node ('docker'){
  stage 'checkout'

  checkout([$class: 'SubversionSCM',
  	additionalCredentials: [],
  	excludedCommitMessages: '',
  	excludedRegions: '',
  	excludedRevprop: '',
  	excludedUsers: '',
  	filterChangelog: false,
  	ignoreDirPropChanges: false,
  	includedRegions: '',
  	locations: [[
  	  credentialsId: '84ee542f-c029-4950-9752-3f2c5111eaec',
  	  depthOption: 'infinity',
  	  ignoreExternalsOption: true,
  	  local: '.',
  	  remote: 'https://lsheiba.svn.cloudforge.com/SwiftTest/branches/httpauth/TestAssertionsChecker'
  	]],
  	workspaceUpdater: [$class: 'UpdateWithCleanUpdater']]
  )

  stage 'build docker image'
  sh 'docker build -t tac .'
}
