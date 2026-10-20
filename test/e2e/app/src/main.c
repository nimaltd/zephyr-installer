/*
 * The application the tests install the demo libraries into, then build and
 * run. It prints what each library answers, and the name set in demo's
 * Kconfig, and stops the build when anything 2.0.0 brings did not arrive.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <app_version.h>

#include "demo.h"
#include "extra.h"

/* Set for the whole build by the library's CMakeLists.txt, not only for its
   own files. */
#ifndef DEMO_DEFINED
#error "DEMO_DEFINED did not reach the application"
#endif

/* VERSION, which extra lists under once, made in the application's folder,
   where Zephyr reads it from. */
#if APP_VERSION_MAJOR != 3
#error "VERSION from extra's once files was not read by Zephyr"
#endif

/* From extra's group placed after find_package(Zephyr), where app exists. */
#ifndef EXTRA_AFTER
#error "EXTRA_AFTER from extra's after-zephyr group did not reach the application"
#endif

/* From extra.conf, which extra's before-zephyr group adds to EXTRA_CONF_FILE. */
#ifndef CONFIG_EXTRA_FROM_CONF
#error "extra.conf, added by extra's before-zephyr group, was not read"
#endif

int main(void)
{
    printk("%s says %d\n", CONFIG_DEMO_NAME, demo_answer());
    printk("extra says %d, version %s\n", extra_answer(), APP_VERSION_STRING);

    return 0;
}
