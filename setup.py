from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in payroll_improvements/__init__.py
from payroll_improvements import __version__ as version

setup(
	name="payroll_improvements",
	version=version,
	description="Improvements to Default Payroll and HR System",
	author="AvN Technologies",
	author_email="info@avntech.net",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
