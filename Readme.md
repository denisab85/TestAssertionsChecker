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
