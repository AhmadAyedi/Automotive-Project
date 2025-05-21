# CMake generated Testfile for 
# Source directory: /home/pi/vsomeip/PFE-2025/mockupWindow/tests
# Build directory: /home/pi/vsomeip/PFE-2025/mockupWindow/tests/build
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(WindowsClientTests "/home/pi/vsomeip/PFE-2025/mockupWindow/tests/build/test_windows_client")
set_tests_properties(WindowsClientTests PROPERTIES  _BACKTRACE_TRIPLES "/home/pi/vsomeip/PFE-2025/mockupWindow/tests/CMakeLists.txt;32;add_test;/home/pi/vsomeip/PFE-2025/mockupWindow/tests/CMakeLists.txt;0;")
subdirs("_deps/googletest-build")
