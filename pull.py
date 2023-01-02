from asyncio import subprocess
from datetime import datetime
from pygit2 import Repository
import ctypes   
import os
import pygit2
import stat
import subprocess
import shutil
import json

TEMP_DIR = '.temp'
MB_SYSTEMMODAL = 0x00001000

class RemoteCallbacks(pygit2.RemoteCallbacks):
    def __init__(self, user, token):
        self.user = user
        self.token = token
    def credentials(self, url, username_from_url, allowed_types):
        return pygit2.UserPass(self.user, self.token)
    def certificate_check(self, certificate, valid, host):
        return True


def pull(info):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    with open('logs.txt', 'a') as logs:
        # Setup Credentials
        callbacks = None
        if info.get("Username") and info.get("Password"):
            callbacks = RemoteCallbacks(info["Username"], info["Password"])
        # Get Changes
        meta, path = {}, info.get("Path", ".")
        try:
            # Is there a remote to pull from?
            if not "URL" in info:
                error(f"No remote URL configured, Please run configure.exe")
                return
            # Path check
            if not os.path.exists(path):
                error(f"Path {path} does not exist, Please run configure.exe")
                return
            # Set path as current directory
            os.chdir(path)
            # Git repo check, if not found, clone it
            if not os.path.exists(f"{path}/.git"):
                pygit2.clone_repository(info["URL"], path, callbacks=callbacks)
            # Check if a temp folder already exists, which it shouldn't
            if os.path.exists(f'../{TEMP_DIR}') and os.path.isdir(f'../{TEMP_DIR}'):
                error(f"Hey! a folder named {TEMP_DIR} already exists in the parent directory. Please remove it and try again.")
                return
            # Copy the .git folder to the temp folder
            shutil.copytree('.git', f'../{TEMP_DIR}/.git', dirs_exist_ok=True)
            # Get git updates in the temp folder
            curr_dir = os.getcwd()
            # Open temp repo to detect changes
            os.chdir(f'../{TEMP_DIR}')
            # Open repo & checkout
            repo = Repository(f"{path}/.git")
            try:
                git_checkout(repo, info.get("Branch", "main"))
            except Exception as ex:
                error(f"Failed to checkout, please reconfigure using config.exe")
                os.chdir(curr_dir)
                rmtree(f'../{TEMP_DIR}')
                return
            # Reset hard & pull
            repo.reset(repo.head.target, pygit2.GIT_RESET_HARD)
            try:
                git_pull(repo, 'origin', info.get("Branch", "main"), callbacks=callbacks)
            except pygit2.GitError as ex:
                if "401" in str(ex):
                    error(f"Failed to get updates from the remote repo, check credentials.")
                else:
                    error(f"Failed to get updates from the remote repo, check your internet connection and try again.")
                os.chdir(curr_dir)
                rmtree(f'../{TEMP_DIR}')
                return
            os.chdir(curr_dir)
            # Check if there are any updates in remote by checking the autopublish file
            if os.path.exists(f'../{TEMP_DIR}/.autopublish'):
                with open(f'../{TEMP_DIR}/.autopublish', 'r') as f:
                    meta = json.load(f)
            rmtree(f'../{TEMP_DIR}')
        except Exception as ex:
            error(f"Failed to get updates into the parent {TEMP_DIR} folder, check permissions and try again.")
            logs.write(str(ex))
            return
        # Check if there are changes
        if info.get("Tag") == meta.get("Tag"):
            logs.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M %p')} Everything is on the version {meta.get('Tag')}!")
            return
        # Prompt user to update
        r = ctypes.windll.user32.MessageBoxW(0, meta.get("UpdateMessage", "Exciting new updates!"), f"Update to {meta.get('Tag', 'v1.0.0')}", 1 | MB_SYSTEMMODAL)
        if r == 1:
            # Open repo & checkout
            repo = Repository(f"{path}/.git")
            try:
                git_checkout(repo, info.get("Branch", "main"))
            except Exception as ex:
                error(f"Failed to checkout, please reconfigure using config.exe")
                return
            # Reset hard & pull
            repo.reset(repo.head.target, pygit2.GIT_RESET_HARD)
            try:
                git_pull(repo, 'origin', info.get("Branch", "main"), callbacks=callbacks)
            except Exception as ex:
                error(f"Failed to get updates from the remote repo, check your internet connection and try again.")
                return
            success(f"Updated to version {meta.get('Tag', 'v1.0.0')}")
        else:
            error(f"Denied an update to {meta.get('Tag', 'v1.0.0')} :(")

def rmtree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)

def error(msg):
    ctypes.windll.user32.MessageBoxW(0, msg, "Error", 0 | MB_SYSTEMMODAL)
    
def success(msg):
    ctypes.windll.user32.MessageBoxW(0, msg, "Yay", 0 | MB_SYSTEMMODAL)

def git_pull(repo: Repository, remote_name='origin', branch='main', callbacks=None):
    for remote in repo.remotes:
        if remote.name == remote_name:
            remote.fetch(callbacks=callbacks)
            remote_master_id = repo.lookup_reference('refs/remotes/origin/%s' % (branch)).target
            merge_result, _ = repo.merge_analysis(remote_master_id)
            # Up to date, do nothing
            if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                return
            # We can just fastforward
            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                repo.checkout_tree(repo.get(remote_master_id))
                try:
                    master_ref = repo.lookup_reference('refs/heads/%s' % (branch))
                    master_ref.set_target(remote_master_id)
                except KeyError:
                    repo.create_branch(branch, repo.get(remote_master_id))
                repo.head.set_target(remote_master_id)
            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                repo.merge(remote_master_id)

                if repo.index.conflicts is not None:
                    for conflict in repo.index.conflicts:
                        print('Conflicts found in:', conflict[0].path)
                    raise AssertionError('Conflicts, ahhhhh!!')

                user = repo.default_signature
                tree = repo.index.write_tree()
                commit = repo.create_commit('HEAD',
                                            user,
                                            user,
                                            'Merge!',
                                            tree,
                                            [repo.head.target, remote_master_id])
                # We need to do this or git CLI will think we are still merging.
                repo.state_cleanup()
            else:
                raise AssertionError('Unknown merge analysis result')

def git_checkout(repo, branch='main'):
    branch = repo.lookup_branch(branch)
    ref = repo.lookup_reference(branch.name)
    repo.checkout(ref)
