/**
 * @file        extra.c
 * @brief       A second library made only to be installed by the tests, with what 2.0.0 brings.
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

#include "extra.h"

/*
 * ****************************************************************************************************
 * Configuration checks
 * ****************************************************************************************************
*/

/* From the group labelled own, which goes into the module's CMakeLists.txt. */
#ifndef EXTRA_OWN
#error "EXTRA_OWN from extra's own group did not reach the library"
#endif

/*
 * ****************************************************************************************************
 * Public function implementations
 * ****************************************************************************************************
*/

/*****************************************************************************************************/
/**
 * @brief 7, from a library built with the define its own group of CMake lines gives it.
 *
 * @return 7.
 */
int extra_answer(void)
{
    return 7;
}
