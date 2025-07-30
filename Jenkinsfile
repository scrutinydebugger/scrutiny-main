pipeline {
    agent {
        label 'docker'
    }
    stages {
        stage ('Docker') {
            agent {
                dockerfile {
                    args '-e HOME=/tmp -e BUILD_CONTEXT=ci --cap-add=NET_ADMIN -u 0:0'
                    additionalBuildArgs '--target build-tests'
                    reuseNode true
                }
            }
            stages {
                stage('Setup vcan'){
                    steps {
                        sh '''
                        ip link add dev vcan0 type vcan || true
                        ip link set up vcan0
                        ip link add dev vcan1 type vcan || true
                        ip link set up vcan1
                        ip link add dev vcan2 type vcan || true
                        ip link set up vcan2
                        ip link add dev vcan3 type vcan || true
                        ip link set up vcan3
                        chown 1000:1000
                        '''
                    }
                }
                stage('Testing'){
                    parallel{
                        stage ('Python 3.13') {
                            steps {
                                sh '''
                                rm -rf venv-3.13
                                python3.13 -m venv venv-3.13
                                SCRUTINY_VENV_DIR=venv-3.13 scripts/with-venv.sh scripts/check-python-version.sh 3.13
                                SCRUTINY_VENV_DIR=venv-3.13 SCRUTINY_COVERAGE_SUFFIX=3.13 UNITTEST_VCAN=vcan0 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.12') {
                            steps {
                                sh '''
                                rm -rf venv-3.12
                                python3.12 -m venv venv-3.12
                                SCRUTINY_VENV_DIR=venv-3.12 scripts/with-venv.sh scripts/check-python-version.sh 3.12
                                SCRUTINY_VENV_DIR=venv-3.12 SCRUTINY_COVERAGE_SUFFIX=3.12 UNITTEST_VCAN=vcan1 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.11') {
                            steps {
                                sh '''
                                rm -rf venv-3.11
                                python3.11 -m venv venv-3.11
                                SCRUTINY_VENV_DIR=venv-3.11 scripts/with-venv.sh scripts/check-python-version.sh 3.11
                                SCRUTINY_VENV_DIR=venv-3.11 SCRUTINY_COVERAGE_SUFFIX=3.11 UNITTEST_VCAN=vcan2 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                        stage ('Python 3.10') {
                            steps {
                                sh '''
                                rm -rf venv-3.10
                                python3.10 -m venv venv-3.10
                                SCRUTINY_VENV_DIR=venv-3.10 scripts/with-venv.sh scripts/check-python-version.sh 3.10
                                SCRUTINY_VENV_DIR=venv-3.10 SCRUTINY_COVERAGE_SUFFIX=3.10 UNITTEST_VCAN=vcan3 scripts/with-venv.sh scripts/runtests.sh
                                '''
                            }
                        }
                    }
                }
                stage("Doc"){
                    steps {
                        sh '''
                        SPHINXOPTS=-W SCRUTINY_VENV_DIR=venv-3.13 scripts/with-venv.sh make -C scrutiny/sdk/docs html
                        '''
                    }
                }
            }
        }
    }
    post {
        // Clean after build
        always {
            cleanWs(cleanWhenNotBuilt: false,
                    deleteDirs: true,
                    disableDeferredWipeout: true,
                    notFailBuild: true,
                    patterns: [[pattern: '.gitignore', type: 'INCLUDE'],
                               [pattern: '.propsfile', type: 'EXCLUDE']])
        }
    }
}
