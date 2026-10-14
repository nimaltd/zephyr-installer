/**
 * @file        demo.c
 * @brief       A library made only to be installed by the tests.
 * @version     1.0.0
 *
 * @author      Nima Askari (NimaLTD)
 * @email       nima.askari@gmail.com
 * @github      https://www.github.com/nimaltd
 * @linkedin    https://www.linkedin.com/in/nimaltd
 * @youtube     https://www.youtube.com/@nimaltd
 * @instagram   https://instagram.com/github.nimaltd
 *
 * @copyright   (c) 2026 Nima Askari (NimaLTD)
 *              SPDX-License-Identifier: Apache-2.0
 *              See LICENSE in the project root for the full license text.
 */

/*
 * ****************************************************************************************************
 * Includes
 * ****************************************************************************************************
*/

#include "demo.h"

/*
 * ****************************************************************************************************
 * Configuration checks
 * ****************************************************************************************************
*/

/* Both come from what zephyr-installer wrote: the setting from the module's
   Kconfig, the define from its CMakeLists.txt. */
#ifndef CONFIG_DEMO_BASE
#error "CONFIG_DEMO_BASE did not reach the library"
#endif

#ifndef DEMO_DEFINED
#error "DEMO_DEFINED did not reach the library"
#endif

/* From zephyr.cmake in installer.yml, for the library's own files only. */
#ifndef DEMO_FROM_CMAKE
#error "DEMO_FROM_CMAKE did not reach the library"
#endif

/*
 * ****************************************************************************************************
 * Public function implementations
 * ****************************************************************************************************
*/

/*****************************************************************************************************/
/**
 * @brief The answer: CONFIG_DEMO_BASE plus 2.
 *
 * @return CONFIG_DEMO_BASE plus 2.
 */
int demo_answer(void)
{
    return CONFIG_DEMO_BASE + 2;
}
