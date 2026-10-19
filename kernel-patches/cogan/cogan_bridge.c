// SPDX-License-Identifier: GPL-2.0-only
/* Cogan's built-in, root-only companion ABI. No vendor ABI/layout changes. */
#include <linux/capability.h>
#include <linux/cpu.h>
#include <linux/cpufreq.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/ktime.h>
#include <linux/list.h>
#include <linux/mutex.h>
#include <linux/pm_qos.h>
#include <linux/slab.h>
#include <linux/sysfs.h>
#include <linux/utsname.h>
#include <linux/workqueue.h>
#include <generated/utsrelease.h>

struct cogan_policy {
	struct list_head node;
	struct cpufreq_policy *policy;
	struct freq_qos_request request;
	s32 requested;
};

static LIST_HEAD(cogan_policies);
static DEFINE_MUTEX(cogan_lock);
static unsigned int big_pct = 100, little_pct = 100;
static u64 deadline;
static int last_error;
static unsigned int clients[2];
static u64 client_seen[2];
static struct kobject *cogan_kobj;
static void cogan_watchdog(struct work_struct *work);
static DECLARE_DEFERRABLE_WORK(cogan_work, cogan_watchdog);

static bool cogan_active(void)
{
	return deadline > ktime_get_boottime_seconds();
}

/* A separate MAX request composes with thermal/vendor/user limits by minimum. */
static int cogan_apply_locked(void)
{
	struct cogan_policy *p;
	unsigned int low = UINT_MAX, high = 0, pct;
	s32 value;
	int ret, error = 0;
	bool active = cogan_active();

	list_for_each_entry(p, &cogan_policies, node) {
		low = min(low, p->policy->cpuinfo.max_freq);
		high = max(high, p->policy->cpuinfo.max_freq);
	}
	list_for_each_entry(p, &cogan_policies, node) {
		pct = low != high && p->policy->cpuinfo.max_freq == low ?
			little_pct : big_pct;
		value = active ? max_t(unsigned int, p->policy->cpuinfo.min_freq,
			(u64)p->policy->cpuinfo.max_freq * pct / 100) :
			FREQ_QOS_MAX_DEFAULT_VALUE;
		ret = freq_qos_update_request(&p->request, value);
		if (ret < 0)
			error = ret;
		else
			p->requested = value;
	}
	last_error = error;
	return error;
}

static int cogan_add_locked(struct cpufreq_policy *policy)
{
	struct cogan_policy *p;
	int ret;

	list_for_each_entry(p, &cogan_policies, node)
		if (p->policy == policy)
			return 0;
	p = kzalloc(sizeof(*p), GFP_KERNEL);
	if (!p)
		return -ENOMEM;
	p->policy = policy;
	p->requested = FREQ_QOS_MAX_DEFAULT_VALUE;
	ret = freq_qos_add_request(&policy->constraints, &p->request,
				 FREQ_QOS_MAX, p->requested);
	if (ret < 0) {
		kfree(p);
		return ret;
	}
	list_add_tail(&p->node, &cogan_policies);
	return 0;
}

static int cogan_policy_event(struct notifier_block *nb,
			      unsigned long event, void *data)
{
	struct cogan_policy *p, *tmp;
	int ret = 0;

	mutex_lock(&cogan_lock);
	if (event == CPUFREQ_CREATE_POLICY)
		ret = cogan_add_locked(data);
	else if (event == CPUFREQ_REMOVE_POLICY)
		list_for_each_entry_safe(p, tmp, &cogan_policies, node) {
			if (p->policy != data)
				continue;
			freq_qos_remove_request(&p->request);
			list_del(&p->node);
			kfree(p);
		}
	if (!ret)
		ret = cogan_apply_locked();
	if (ret)
		last_error = ret;
	mutex_unlock(&cogan_lock);
	return NOTIFY_OK;
}

static struct notifier_block cogan_nb = { .notifier_call = cogan_policy_event };

static ssize_t abi_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	return sysfs_emit(buf, "1\n");
}

/* Compile-time constants: SUSFS's uname/UTS spoof cannot rewrite these. */
static ssize_t release_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	return sysfs_emit(buf, "%s\n", UTS_RELEASE);
}

static ssize_t banner_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	return sysfs_emit(buf, "%s", linux_banner);
}

static ssize_t features_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	return sysfs_emit(buf, "bridge=1 cpu_qos=1 susfs=%d nomount=%d bbg=%d\n",
		IS_ENABLED(CONFIG_KSU_SUSFS), IS_ENABLED(CONFIG_NOMOUNT),
		IS_ENABLED(CONFIG_BBG));
}

static ssize_t limits_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	struct cogan_policy *p;
	unsigned int n = 0;
	u64 now = ktime_get_boottime_seconds();
	ssize_t len;

	mutex_lock(&cogan_lock);
	list_for_each_entry(p, &cogan_policies, node)
		n++;
	len = sysfs_emit(buf, "%u %u %llu %u %d\n", big_pct, little_pct,
		deadline > now ? deadline - now : 0, n, last_error);
	mutex_unlock(&cogan_lock);
	return len;
}

static ssize_t limits_store(struct kobject *k, struct kobj_attribute *a,
			    const char *buf, size_t count)
{
	unsigned int big, little, ttl;
	char extra;
	int ret;

	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	if (sscanf(buf, "%u %u %u %c", &big, &little, &ttl, &extra) != 3)
		return -EINVAL;
	if (!(big == 0 && little == 0 && ttl == 0) &&
	    (big < 20 || big > 100 || little < 20 || little > 100 ||
	     ttl < 5 || ttl > 180))
		return -ERANGE;
	mutex_lock(&cogan_lock);
	if (ttl && list_empty(&cogan_policies)) {
		mutex_unlock(&cogan_lock);
		return -ENODEV;
	}
	big_pct = ttl ? big : 100;
	little_pct = ttl ? little : 100;
	deadline = ttl ? ktime_get_boottime_seconds() + ttl : 0;
	ret = cogan_apply_locked();
	if (ret < 0) {
		deadline = 0;
		cogan_apply_locked();
		last_error = ret;
	}
	mutex_unlock(&cogan_lock);
	if (ttl && !ret)
		mod_delayed_work(system_wq, &cogan_work, 5 * HZ);
	return ret < 0 ? ret : count;
}

static ssize_t policies_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	struct cogan_policy *p;
	int len = 0;

	mutex_lock(&cogan_lock);
	list_for_each_entry(p, &cogan_policies, node) {
		if (len >= PAGE_SIZE - 80)
			break;
		len += sysfs_emit_at(buf, len, "%u %d %d\n", p->policy->cpu,
			p->requested, freq_qos_read_value(&p->policy->constraints,
						 FREQ_QOS_MAX));
	}
	mutex_unlock(&cogan_lock);
	return len;
}

static ssize_t client_show(struct kobject *k, struct kobj_attribute *a, char *buf)
{
	unsigned int i = !strcmp(a->attr.name, "thermal_client");
	u64 age;
	ssize_t len;

	mutex_lock(&cogan_lock);
	age = clients[i] ? ktime_get_boottime_seconds() - client_seen[i] : 0;
	len = sysfs_emit(buf, "%u %llu\n", age <= 900 ? clients[i] : 0, age);
	mutex_unlock(&cogan_lock);
	return len;
}

static ssize_t client_store(struct kobject *k, struct kobj_attribute *a,
			    const char *buf, size_t count)
{
	unsigned int code, i = !strcmp(a->attr.name, "thermal_client");

	if (!capable(CAP_SYS_ADMIN))
		return -EPERM;
	if (kstrtouint(buf, 10, &code) || code > 1000000)
		return -EINVAL;
	mutex_lock(&cogan_lock);
	clients[i] = code;
	client_seen[i] = ktime_get_boottime_seconds();
	mutex_unlock(&cogan_lock);
	return count;
}

static struct kobj_attribute abi_attr = __ATTR(abi, 0400, abi_show, NULL);
static struct kobj_attribute release_attr = __ATTR(release, 0400, release_show, NULL);
static struct kobj_attribute banner_attr = __ATTR(banner, 0400, banner_show, NULL);
static struct kobj_attribute features_attr = __ATTR(features, 0400, features_show, NULL);
static struct kobj_attribute limits_attr = __ATTR(limits, 0600, limits_show, limits_store);
static struct kobj_attribute policies_attr = __ATTR(policies, 0400, policies_show, NULL);
static struct kobj_attribute power_attr = __ATTR(power_client, 0600, client_show, client_store);
static struct kobj_attribute thermal_attr = __ATTR(thermal_client, 0600, client_show, client_store);
static struct attribute *cogan_attrs[] = {
	&abi_attr.attr, &release_attr.attr, &banner_attr.attr, &features_attr.attr,
	&limits_attr.attr, &policies_attr.attr, &power_attr.attr, &thermal_attr.attr, NULL
};
static const struct attribute_group cogan_group = { .attrs = cogan_attrs };

static void cogan_watchdog(struct work_struct *work)
{
	mutex_lock(&cogan_lock);
	if (deadline && !cogan_active()) {
		deadline = 0;
		cogan_apply_locked();
	}
	if (deadline)
		schedule_delayed_work(&cogan_work, 5 * HZ);
	mutex_unlock(&cogan_lock);
}

static int __init cogan_init(void)
{
	struct cpufreq_policy *policy;
	struct cogan_policy *p, *tmp;
	unsigned int cpu;
	int ret;

	ret = cpufreq_register_notifier(&cogan_nb, CPUFREQ_POLICY_NOTIFIER);
	if (ret)
		return ret;
	cpus_read_lock();
	for_each_possible_cpu(cpu) {
		policy = cpufreq_cpu_get(cpu);
		if (!policy)
			continue;
		mutex_lock(&cogan_lock);
		ret = cogan_add_locked(policy);
		mutex_unlock(&cogan_lock);
		cpufreq_cpu_put(policy);
		if (ret)
			break;
	}
	cpus_read_unlock();
	if (ret)
		goto fail;
	cogan_kobj = kobject_create_and_add("cogan", kernel_kobj);
	if (!cogan_kobj) {
		ret = -ENOMEM;
		goto fail;
	}
	ret = sysfs_create_group(cogan_kobj, &cogan_group);
	if (ret) {
		kobject_put(cogan_kobj);
		goto fail;
	}
	return 0;
fail:
	cpufreq_unregister_notifier(&cogan_nb, CPUFREQ_POLICY_NOTIFIER);
	list_for_each_entry_safe(p, tmp, &cogan_policies, node) {
		freq_qos_remove_request(&p->request);
		list_del(&p->node);
		kfree(p);
	}
	return ret;
}
late_initcall(cogan_init);
