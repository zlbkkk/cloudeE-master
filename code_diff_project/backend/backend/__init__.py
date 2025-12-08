import pymysql
pymysql.install_as_MySQLdb()

# Monkey patch to bypass MySQL version check
from django.db.backends.mysql.base import DatabaseWrapper
DatabaseWrapper.check_database_version_supported = lambda self: None
