#!/usr/bin/env python

import sys
import datetime

import tac_project
import tac_common


#
# Main
#
def main():
    params = tac_common.Arguments()
    log = tac_common.Logger(params.log_file, params.verbose)
    projects = []
    passed = 0
    failed = 0
    aborted = 0
    total_duration = 0
    log.separator()
    log.verbose("The following folders have been added to execution list:")
    for dir in params.folders:
        log.verbose(dir)
    log.verbose("\n")
    for dir in params.folders:
        project = tac_project.LdxProject(dir, params, log)
        if project:
            projects.append(project)
            total_duration += project.duration()
    total_duration = datetime.timedelta(seconds=total_duration/1000)
    finish_time = datetime.datetime.now() + total_duration
    log.info('Number of tests to run:   %s' % len(params.folders))
    log.info('Estimated total duration: %s' % total_duration)
    log.info('Estimated finish time:    %s' % finish_time.strftime("%H:%M:%S %d.%m.%y"))
    for project in projects:
        log.separator()
        if not (project.load()):
            log.warning('Skipping project')
            continue
        if project.run():
            if project.check():
                log.info('"%s" passed' % project.project_dir)
                passed += 1
            else:
                log.info('"%s" failed' % project.project_dir)
                failed += 1
        else:
            log.info('"%s" aborted' % project.project_dir)
            aborted += 1

    log.info('\tTotal attempted: ' + str(passed + failed + aborted))
    log.info('\tTotal passed:    ' + tac_common.Bcolors.OK + str(passed) + tac_common.Bcolors.ENDC)
    log.info('\tTotal aborted:   ' + tac_common.Bcolors.ABORT + str(aborted) + tac_common.Bcolors.ENDC)
    log.info('\tTotal failed:    ' + tac_common.Bcolors.FAIL + str(failed) + tac_common.Bcolors.ENDC)
    log.info('Test finished at:  ' + datetime.datetime.now().strftime("%H:%M:%S %d.%m.%y"))

    if (failed == 0) and (aborted == 0):
        sys.exit(0)
    else:
        sys.exit(2)

if __name__ == '__main__':
    main()
