# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.25

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /usr/bin/cmake

# The command to remove a file.
RM = /usr/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /home/pi/vsomeip/PFE-2025/mockupWindow

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /home/pi/vsomeip/PFE-2025/mockupWindow/build

# Include any dependencies generated for this target.
include CMakeFiles/client-mockupWindow.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include CMakeFiles/client-mockupWindow.dir/compiler_depend.make

# Include the progress variables for this target.
include CMakeFiles/client-mockupWindow.dir/progress.make

# Include the compile flags for this target's objects.
include CMakeFiles/client-mockupWindow.dir/flags.make

CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o: CMakeFiles/client-mockupWindow.dir/flags.make
CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o: /home/pi/vsomeip/PFE-2025/mockupWindow/src/client-mockupWindow.cpp
CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o: CMakeFiles/client-mockupWindow.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/pi/vsomeip/PFE-2025/mockupWindow/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o"
	/usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o -MF CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o.d -o CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o -c /home/pi/vsomeip/PFE-2025/mockupWindow/src/client-mockupWindow.cpp

CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing CXX source to CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.i"
	/usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/pi/vsomeip/PFE-2025/mockupWindow/src/client-mockupWindow.cpp > CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.i

CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling CXX source to assembly CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.s"
	/usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/pi/vsomeip/PFE-2025/mockupWindow/src/client-mockupWindow.cpp -o CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.s

# Object files for target client-mockupWindow
client__mockupWindow_OBJECTS = \
"CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o"

# External object files for target client-mockupWindow
client__mockupWindow_EXTERNAL_OBJECTS =

client-mockupWindow: CMakeFiles/client-mockupWindow.dir/src/client-mockupWindow.cpp.o
client-mockupWindow: CMakeFiles/client-mockupWindow.dir/build.make
client-mockupWindow: /usr/local/lib/libvsomeip3.so.3.5.4
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_system.so.1.74.0
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_log.so.1.74.0
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_thread.so.1.74.0
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_atomic.so.1.74.0
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_chrono.so.1.74.0
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_filesystem.so.1.74.0
client-mockupWindow: /usr/lib/aarch64-linux-gnu/libboost_regex.so.1.74.0
client-mockupWindow: CMakeFiles/client-mockupWindow.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/pi/vsomeip/PFE-2025/mockupWindow/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable client-mockupWindow"
	$(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/client-mockupWindow.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
CMakeFiles/client-mockupWindow.dir/build: client-mockupWindow
.PHONY : CMakeFiles/client-mockupWindow.dir/build

CMakeFiles/client-mockupWindow.dir/clean:
	$(CMAKE_COMMAND) -P CMakeFiles/client-mockupWindow.dir/cmake_clean.cmake
.PHONY : CMakeFiles/client-mockupWindow.dir/clean

CMakeFiles/client-mockupWindow.dir/depend:
	cd /home/pi/vsomeip/PFE-2025/mockupWindow/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/pi/vsomeip/PFE-2025/mockupWindow /home/pi/vsomeip/PFE-2025/mockupWindow /home/pi/vsomeip/PFE-2025/mockupWindow/build /home/pi/vsomeip/PFE-2025/mockupWindow/build /home/pi/vsomeip/PFE-2025/mockupWindow/build/CMakeFiles/client-mockupWindow.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : CMakeFiles/client-mockupWindow.dir/depend

