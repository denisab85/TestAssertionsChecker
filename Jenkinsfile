node ('docker'){
  stage 'checkout'

  checkout([$class: 'GitSCM',
    branches: [[name: '*/master']],
    doGenerateSubmoduleConfigurations: false,
    extensions: [],
    submoduleCfg: [],
    userRemoteConfigs: [[url: 'https://github.com/denisab85/TestAssertionsChecker.git']]])

  stage 'build docker image'
  sh 'docker build -t tac .'
}
