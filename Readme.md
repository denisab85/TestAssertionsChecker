# TestAssertionsChecker (TAC)

TAC is a python application for running multiple LoadDynamix test projects and verifying their results against
user-defined rules.
TAC uses swifttest API to convert LoadDynamix test projects into AutomationConfig and run them against appliances.
LoadDynamix test projects are meant to have been created using the TDE program or any other means.


TAC consists of the following files:
tac.py             - the main executive, an entry point to the program;
tac_project.py     - module to deal with (convert, run) LoadDynamix projects using swifttest API;
tac_assertions.py  - module to process verification of summary files against assertions;
tac_calculation.py - module to handle mathematical calculation of expressions (tokens);
tac_common.py      - module to handle command line arguments, logging and other general-purpose procedures.

## Command-line arguments
See `tac.py -h`

## Format of test list file (parameter --test_list)
This file passed to TAC sets paths to test project to be executed.
The file should be in JSON format.
Its topmost level should be a list [] of dictionaries {}.
The only mandatory field in each dictionary is "name". Its user-assigned value identifies the name of the test set.
To enable a certain test set, its name should be added to the -T parameter. 
Paths to test projects in each set are contained in the "roots" sub-item.
The latter consists of the mandatory "name" pointing to the root folder and "paths" listing relative paths to tests.
At each level of the JSON file, the optional "comment" and "runs" parameters can be used, 
with "runs" setting the number of times this section will be added to the resulting execution list.
The numbers in "runs" at each level are multiplied when it comes to actual test path. 
Thus, if "runs" is set to 2 at the topmost level, to 3 at the roots level and to 4 at the paths level, 
each test in this "paths" will be added 24 times. If not explicitly set, "runs" defaults to 1.
Topmost level items with the same name would be combined, thus giving one extended set of tests, identified by this item's name.
Also, several roots can be used under the same test set record.
A root folder containing a path with "name" set to "\*" (asterisk) will be extended to include all subfolders of the root.
All other paths in this root will be ignored. 

## Verification of assertions
To verify project results, TAC uses summary files (.sum or .summary) which are downloaded automatically after a project
run. The numbers read from these files are used.

## Build a TAC Docker image
`docker build -t tac .`

You can pass arguments at build-time using the `--build-arg <varname>=<value>` flag. See Dockerfile for avialable arguments.

## Run TAC Docker container
```
docker run \
  -it \
  --rm \
  -v /path/to/SampleTests:/tmp/smpltests \
  -v /path/to/Ports:/opt/swifttest/resources/dotnet/Ports:ro \
  tac
```
Useful options (more at https://docs.docker.com/engine/reference/run/):  
  `-d`  start a container in detached mode (conflict with `-i` option)  
  `-i` keep STDIN open even if not attached  
  `-t` allocate a pseudo-tty

## Run tests in docker container
```
docker run \
  -it
  -v /path/to/SampleTests:/tmp/smpltests \
  -v /path/to/Ports:/opt/swifttest/resources/dotnet/Ports:ro \
  tac python tac.py "/tmp/smpltests/test_name1" "/tmp/smpltests/test_name2" "/tmp/smpltests/test_nameN"
```
