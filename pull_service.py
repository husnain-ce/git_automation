from datetime import datetime
from pygit2 import Repository
import os
import pygit2
import stat
import shutil
import sys
import time
import json
import win32serviceutil  # ServiceFramework and commandline helper
import win32service  # Events
import win32ts
from win32con import MB_SERVICE_NOTIFICATION
import servicemanager  # Simple setup and logging

TEMP_DIR = '.temp'
MB_SYSTEMMODAL = 0x00001000

class UpdaterService:
    """
    A simple service that runs a loop every X minutes.
    """
    def init_config(self) -> None:
        self.args = {}
        try:
            if os.path.exists(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config")):
                with open(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config"), 'r') as f:
                    self.args = json.load(f)
            if os.path.exists(os.path.join(self.args.get("Path", ""), ".autopublish")):
                with open(os.path.join(self.args.get("Path", ""), ".autopublish"), 'r') as f:
                    self.args.update(json.load(f))
        except Exception:
            pass

    def stop(self):
        """Stop the service"""
        self.running = False

    def run(self):
        """Main service loop. This is where work is done!"""
        self.running = True
        self.init_config()
        with open(os.path.join(self.args.get("Path", ""), "logs.txt"), 'a') as logs:
            logs.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M %p')} Starting service\n")
            # Take ownership of git folder
            try:
                if os.path.exists(os.path.join(self.args.get("Path", ""), ".git")):
                    shutil.copytree(os.path.join(self.args["Path"], ".git"), os.path.join(self.args["Path"], "temp.git"), copy_function=shutil.copyfile)
                    rmtree(os.path.join(self.args["Path"], ".git"))
                    os.rename(os.path.join(self.args["Path"], "temp.git"), os.path.join(self.args["Path"], ".git"))
            except Exception as ex:
                console_session = win32ts.WTSGetActiveConsoleSessionId()
                error("Error while copying git folder, update service will not start", console_session)
                logs.write(str(ex) + "\n")
        while self.running:
            servicemanager.LogInfoMsg("Service running...")
            try:
                pull(self.args)
            except Exception as ex:
                with open(os.path.join(self.args.get("Path", ""), "logs.txt"), "a") as logs:
                    logs.write(str(ex) + "\n")
            time.sleep(self.args.get('Wait', 1) * 60)
            self.init_config()

class AppUpdaterServiceFramework(win32serviceutil.ServiceFramework):

    _svc_name_ = 'AppUpdaterService'
    _svc_display_name_ = 'App Updater Service'
    _svc_description_ = 'Auto update application'

    def SvcStop(self):
        """Stop the service"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.service_impl.stop()
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        """Start the service; does not return until stopped"""
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.service_impl = UpdaterService()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        # Run the service
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.service_impl.run()


def init():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppUpdaterServiceFramework)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AppUpdaterServiceFramework)


class RemoteCallbacks(pygit2.RemoteCallbacks):
    def __init__(self, user, token):
        self.user = user
        self.token = token
    def credentials(self, url, username_from_url, allowed_types):
        return pygit2.UserPass(self.user, self.token)
    def certificate_check(self, certificate, valid, host):
        return True


def pull(info):
    console_session = win32ts.WTSGetActiveConsoleSessionId()
    with open(os.path.join(info.get("Path", ""), "logs.txt"), 'a') as logs:
        # Setup Credentials
        callbacks = None
        if info.get("Username") and info.get("Password"):
            callbacks = RemoteCallbacks(info["Username"], info["Password"])
        # Get Changes
        meta, path = {}, info.get("Path", None)
        try:
            # Is there a remote to pull from?
            if not "URL" in info or "Path" not in info:
                error(f"No remote URL or Path configured, Please run configure.exe", console_session)
                return
            # Path check
            if not os.path.exists(path):
                error(f"Path {path} does not exist, Please run configure.exe", console_session)
                return
            # Set path as current directory
            os.chdir(path)
            # Check if a temp folder already exists, which it shouldn't
            if os.path.exists(f'../{TEMP_DIR}') and os.path.isdir(f'../{TEMP_DIR}'):
                error(f"Hey! a folder named {TEMP_DIR} already exists in the parent directory. Please remove it and try again.", console_session)
                return
            # Git repo check, if not found, clone it
            if not os.path.exists(os.path.join(path, ".git")):
                pygit2.clone_repository(info["URL"], os.path.join(path, "..", TEMP_DIR), callbacks=callbacks)
                shutil.copytree(os.path.join(path, "..", TEMP_DIR), os.path.join(path), dirs_exist_ok=True)
                rmtree(os.path.join(path, "..", TEMP_DIR))
                return
            # Copy the .git folder to the temp folder
            shutil.copytree(os.path.join(path, ".git"), os.path.join(path, "..", TEMP_DIR, ".git"), dirs_exist_ok=True)
            # Open repo & checkout
            repo = Repository(os.path.join(path, "..", TEMP_DIR, ".git"))
            try:
                git_checkout(repo, info.get("Branch", "main"))
            except Exception as ex:
                error(f"Failed to checkout, please reconfigure using config.exe", console_session)
                repo.free()
                rmtree(os.path.join(path, "..", TEMP_DIR))
                return
            # Reset hard & pull
            repo.reset(repo.head.target, pygit2.GIT_RESET_HARD)
            try:
                git_pull(repo, 'origin', info.get("Branch", "main"), callbacks=callbacks)
            except pygit2.GitError as ex:
                if "401" in str(ex):
                    error(f"Failed to get updates from the remote repo, check credentials.", console_session)
                else:
                    error(f"Failed to get updates from the remote repo, check your internet connection and try again.", console_session)
                repo.free()
                rmtree(os.path.join(path, "..", TEMP_DIR))
                return
            # Check if there are any updates in remote by checking the autopublish file
            if os.path.exists(os.path.join(path, "..", TEMP_DIR, ".autopublish")):
                with open(os.path.join(path, "..", TEMP_DIR, ".autopublish"), 'r') as f:
                    meta = json.load(f)
            repo.free()
            rmtree(os.path.join(path, "..", TEMP_DIR))
        except Exception as ex:
            error(f"Failed to get updates into the parent {TEMP_DIR} folder, check permissions and try again.", console_session)
            logs.write(str(ex) + "\n")
            repo.free()
            return
        # Check if there are changes
        if info.get("Tag") == meta.get("Tag"):
            logs.write(f"{datetime.now().strftime('%d-%m-%Y %H:%M %p')} Everything is on the version {meta.get('Tag')}!\n")
            return
        # Prompt user to update
        #r = ctypes.windll.user32.MessageBoxW(0, meta.get("UpdateMessage", "Exciting new updates!"), f"Update to {meta.get('Tag', 'v1.0.0')}", 1 | MB_SYSTEMMODAL)
        #r = win32ui.MessageBox(meta.get("UpdateMessage", "Exciting new updates!"), f"Update to {meta.get('Tag', 'v1.0.0')}", 1 | MB_SYSTEMMODAL | MB_SERVICE_NOTIFICATION)
        r =  win32ts.WTSSendMessage(win32ts.WTS_CURRENT_SERVER_HANDLE, console_session, f"Update to {meta.get('Tag', 'v1.0.0')}", meta.get("UpdateMessage", "Exciting new updates!"), 1 | MB_SYSTEMMODAL | MB_SERVICE_NOTIFICATION, 15, True)
        if r == 1:
            # Open repo & checkout
            repo = Repository(os.path.join(path, ".git"))
            try:
                git_checkout(repo, info.get("Branch", "main"))
            except Exception as ex:
                error(f"Failed to checkout, please reconfigure using config.exe", console_session)
                repo.free()
                return
            # Reset hard & pull
            repo.reset(repo.head.target, pygit2.GIT_RESET_HARD)
            try:
                git_pull(repo, 'origin', info.get("Branch", "main"), callbacks=callbacks)
            except Exception as ex:
                error(f"Failed to get updates from the remote repo, check your internet connection and try again.", console_session)
                repo.free()
                return
            repo.free()
            success(f"Updated to version {meta.get('Tag', 'v1.0.0')}", console_session)
        else:
            error(f"Denied an update to {meta.get('Tag', 'v1.0.0')} :(", console_session)

def rmtree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWUSR)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)

def error(msg, console_session):
    win32ts.WTSSendMessage(win32ts.WTS_CURRENT_SERVER_HANDLE, console_session, "Error", msg, 0 | MB_SYSTEMMODAL | MB_SERVICE_NOTIFICATION, 0, False)
    #win32ui.MessageBox(msg, "Error", 0 | MB_SYSTEMMODAL | MB_SERVICE_NOTIFICATION)
    
def success(msg, console_session):
    win32ts.WTSSendMessage(win32ts.WTS_CURRENT_SERVER_HANDLE, console_session, "Yay", msg, 0 | MB_SYSTEMMODAL | MB_SERVICE_NOTIFICATION, 0, False)
    #win32ui.MessageBox(msg, "Yay", 0 | MB_SYSTEMMODAL | MB_SERVICE_NOTIFICATION)

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

if __name__ == '__main__':
    # UpdaterService().run()
    args = {}
    if os.path.exists(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config")):
        with open(os.path.join("C:\\", "ProgramData", "autoupdater", ".autopublish.config"), 'r') as f:
            args = json.load(f)
    if os.path.exists(os.path.join(args.get("Path", ""), ".autopublish")):
        with open(os.path.join(args.get("Path", ""), ".autopublish"), 'r') as f:
            args.update(json.load(f))
    pull(args)

