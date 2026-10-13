/*
 * The application the tests install the demo library into, then build and
 * run. It prints what the library answers, and the name set in its Kconfig.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "demo.h"

/* Set for the whole build by the library's CMakeLists.txt, not only for its
   own files. */
#ifndef DEMO_DEFINED
#error "DEMO_DEFINED did not reach the application"
#endif

int main(void)
{
    printk("%s says %d\n", CONFIG_DEMO_NAME, demo_answer());

    return 0;
}
