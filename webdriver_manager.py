import requests
import wget
import zipfile
import os

from regex import regex


# first check if chromedriver is already in the path
# if not, download it
# if it is, check if it's the latest version
# if not, download the latest version


def get_chromedriver_path():
    # get with which
    # check if chromedriver is in the path
    if os.name == 'nt':
        return os.popen('where chromedriver').read().strip()
    elif os.name == 'posix':
        return os.popen('which chromedriver').read().strip()


def version_str_to_tuple(version_str):
    return tuple(map(int, version_str.split('.')))


def check_system_chromedriver_version():
    chromedriver_path = get_chromedriver_path()

    # get the version number of the system chromedriver
    response = os.popen(f'{chromedriver_path} --version').read()
    # match the version number with the regex
    match = regex.match(r'ChromeDriver (?P<version>\d+\.\d+\.\d+\.\d+)', response)
    if match:
        return version_str_to_tuple(match.group('version'))
    else:
        raise Exception('Could not get system chromedriver version')


def check_latest_chromedriver_version():
    # get the latest chromedriver version number
    url = 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE'
    response = requests.get(url)
    version_number = response.text
    return version_str_to_tuple(version_number)


def get_chromedriver_url():
    # get the latest chrome driver version number
    url = 'https://chromedriver.storage.googleapis.com/LATEST_RELEASE'
    response = requests.get(url)
    version_number = response.text

    # check os:
    if os.name == 'nt':
        os_name = 'win32'
    elif os.name == 'posix':
        # check if mac or linux
        if os.uname().sysname == 'Darwin':
            if os.uname().machine == 'x86_64':
                os_name = 'mac64'
            elif os.uname().machine == 'arm64':
                os_name = 'mac64_m1'
            else:
                raise Exception('Unknown Mac architecture')
        else:
            os_name = 'linux64'
    else:
        raise Exception('Unknown OS')

    return f"https://chromedriver.storage.googleapis.com/{version_number}/chromedriver_{os_name}.zip"
