## This file should be placed in the root directory of your project.
## Then modify the CMakeLists.txt file in the root directory of your
## project to incorporate the testing dashboard.

set(CTEST_PROJECT_NAME "Beta-Beat")
set(CTEST_NIGHTLY_START_TIME "00:00:00 CET")
set(CTEST_DROP_METHOD "http")
set(CTEST_DROP_SITE "ylevinse.web.cern.ch/ylevinse")
set(CTEST_DROP_LOCATION "/cdash/submit.php?project=Beta-Beat")
set(CTEST_DROP_SITE_CDASH TRUE)
set(UPDATE_TYPE "git")

