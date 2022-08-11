export

# ---------------- BEFORE RELEASE ----------------
# 1 - Update Version Number
# 2 - Update RELEASE.md
# 3 - make update_setup
# -------------- Release Process Steps --------------
# 1 - Get Credentials from devops-accounts repo
# 2 - Create Release Branch and push
# 3 - Create Release Tag and push
# 4 - GitHub Release
# 5 - PyPI Release

########################################################
# 		Variables
########################################################

# MUST BE THE SAME AS API in Mayor and Minor Version Number
# example: API 2.9.0 --> Client 2.9.X
ONDEWO_VTSI_API_VERSION=3.0.0
ONDEWO_NLU_API_GIT_BRANCH=tags/2.10.0
ONDEWO_S2T_API_GIT_BRANCH=tags/3.3.0
ONDEWO_T2S_API_GIT_BRANCH=tags/4.3.0
ONDEWO_SIP_API_GIT_BRANCH=tags/3.1.0
ONDEWO_NLU_DIR=ondewo-nlu-api
ONDEWO_S2T_DIR=ondewo-s2t-api
ONDEWO_T2S_DIR=ondewo-t2s-api
ONDEWO_SIP_DIR=ondewo-sip-api

# You need to setup an access token at https://github.com/settings/tokens - permissions are important
GITHUB_GH_TOKEN?=ENTER_YOUR_TOKEN_HERE

CURRENT_RELEASE_NOTES=`cat RELEASE.md \
	| sed -n '/Release ONDEWO VTSI APIS ${ONDEWO_VTSI_API_VERSION}/,/\*\*/p'`

GH_REPO="https://github.com/ondewo/ondewo-vtsi-api"
DEVOPS_ACCOUNT_GIT="ondewo-devops-accounts"
DEVOPS_ACCOUNT_DIR="./${DEVOPS_ACCOUNT_GIT}"
IMAGE_UTILS_NAME=ondewo-vtsi-api-utils:${ONDEWO_VTSI_API_VERSION}
.DEFAULT_GOAL := help

########################################################
#       ONDEWO Standard Make Targets
########################################################

setup_developer_environment_locally: install_precommit_hooks install_dependencies_locally

install_precommit_hooks: ## Installs pre-commit hooks and sets them up for the ondewo-vtsi-api repo
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg

precommit_hooks_run_all_files: ## Runs all pre-commit hooks on all files and not just the changed ones
	pre-commit run --all-file

help: ## Print usage info about help targets
	# (first comment after target starting with double hashes ##)
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-40s\033[0m %s\n", $$1, $$2}'

makefile_chapters: ## Shows all sections of Makefile
	@echo `cat Makefile| grep "########################################################" -A 1 | grep -v "########################################################"`

TEST:
	@echo ${GITHUB_GH_TOKEN}
	@echo ${CURRENT_RELEASE_NOTES}

########################################################
#       Repo Specific Make Targets
########################################################
#		Submodules

build: init_submodules checkout_defined_submodule_versions ## Checks out and copys submodule protos to ondewo directory

init_submodules:  ## Initialize submodules
	@echo "START initializing submodules ..."
	git submodule update --init --recursive
	@echo "DONE initializing submodules"

checkout_defined_submodule_versions:  ## Update submodule versions
	@echo "START checking out submodules ..."
	git -C ${ONDEWO_T2S_DIR} fetch --all
	git -C ${ONDEWO_T2S_DIR} checkout ${ONDEWO_T2S_API_GIT_BRANCH}
	git -C ${ONDEWO_NLU_DIR} fetch --all
	git -C ${ONDEWO_NLU_DIR} checkout ${ONDEWO_NLU_API_GIT_BRANCH}
	git -C ${ONDEWO_S2T_DIR} fetch --all
	git -C ${ONDEWO_S2T_DIR} checkout ${ONDEWO_S2T_API_GIT_BRANCH}
	git -C ${ONDEWO_SIP_DIR} fetch --all
	git -C ${ONDEWO_SIP_DIR} checkout ${ONDEWO_SIP_API_GIT_BRANCH}
	if [ -d googleapis ]; then rm -Rf googleapis; fi
	if [ -d ondewo/nlu ]; then rm -Rf ondewo/nlu; fi
	if [ -d ondewo/s2t ]; then rm -Rf ondewo/s2t; fi
	if [ -d ondewo/t2s ]; then rm -Rf ondewo/t2s; fi
	if [ -d ondewo/sip ]; then rm -Rf ondewo/sip; fi
	if [ -d ondewo/qa ]; then rm -Rf ondewo/sip; fi
	cp -r "${ONDEWO_NLU_DIR}/googleapis" .
	cp -r "${ONDEWO_NLU_DIR}/ondewo/nlu" ondewo
	cp -r "${ONDEWO_NLU_DIR}/ondewo/qa" ondewo
	cp -r "${ONDEWO_T2S_DIR}/ondewo/t2s" ondewo
	cp -r "${ONDEWO_S2T_DIR}/ondewo/s2t" ondewo
	cp -r "${ONDEWO_SIP_DIR}/ondewo/sip" ondewo

########################################################
#		Release

release: create_release_branch create_release_tag build_and_release_to_github_via_docker  ## Automate the entire release process
	@echo "Release Finished"

create_release_branch: ## Create Release Branch and push it to origin
	git checkout -b "release/${ONDEWO_VTSI_API_VERSION}"
	git push -u origin "release/${ONDEWO_VTSI_API_VERSION}"

create_release_tag: ## Create Release Tag and push it to origin
	git tag -a ${ONDEWO_VTSI_API_VERSION} -m "release/${ONDEWO_VTSI_API_VERSION}"
	git push origin ${ONDEWO_VTSI_API_VERSION}

login_to_gh: ## Login to Github CLI with Access Token
	echo $(GITHUB_GH_TOKEN) | gh auth login -p ssh --with-token

build_gh_release: ## Generate Github Release with CLI
	gh release create --repo $(GH_REPO) "$(ONDEWO_VTSI_API_VERSION)" -n "$(CURRENT_RELEASE_NOTES)" -t "Release ${ONDEWO_VTSI_API_VERSION}"

########################################################
#		GITHUB

build_and_release_to_github_via_docker: build_utils_docker_image release_to_github_via_docker_image  ## Release automation for building and releasing on GitHub via a docker image

build_utils_docker_image:  ## Build utils docker image
	docker build -f Dockerfile.utils -t ${IMAGE_UTILS_NAME} .

push_to_gh: login_to_gh build_gh_release
	@echo 'Released to Github'

release_to_github_via_docker_image:  ## Release to Github via docker
	docker run --rm \
		-e GITHUB_GH_TOKEN=${GITHUB_GH_TOKEN} \
		${IMAGE_UTILS_NAME} make push_to_gh

########################################################
#		DEVOPS-ACCOUNTS

ondewo_release: spc clone_devops_accounts run_release_with_devops ## Release with credentials from devops-accounts repo
	@rm -rf ${DEVOPS_ACCOUNT_GIT}

clone_devops_accounts: ## Clones devops-accounts repo
	if [ -d $(DEVOPS_ACCOUNT_GIT) ]; then rm -Rf $(DEVOPS_ACCOUNT_GIT); fi
	git clone git@bitbucket.org:ondewo/${DEVOPS_ACCOUNT_GIT}.git

run_release_with_devops:
	$(eval info:= $(shell cat ${DEVOPS_ACCOUNT_DIR}/account_github.env | grep GITHUB_GH & cat ${DEVOPS_ACCOUNT_DIR}/account_pypi.env | grep PYPI_USERNAME & cat ${DEVOPS_ACCOUNT_DIR}/account_pypi.env | grep PYPI_PASSWORD))
	make release $(info)

spc: ## Checks if the Release Branch and Tag already exist
	$(eval filtered_branches:= $(shell git branch --all | grep "release/${ONDEWO_VTSI_API_VERSION}"))
	$(eval filtered_tags:= $(shell git tag --list | grep "${ONDEWO_VTSI_API_VERSION}"))
	@if test "$(filtered_branches)" != ""; then echo "-- Test 1: Branch exists!!" & exit 1; else echo "-- Test 1: Branch is fine";fi
	@if test "$(filtered_tags)" != ""; then echo "-- Test 2: Tag exists!!" & exit 1; else echo "-- Test 2: Tag is fine";fi
