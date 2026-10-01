import pymysql

# Let Django use PyMySQL as its MySQL DB-API driver. This avoids Windows
# mysqlclient TLS-provider issues when connecting to TiDB Cloud.
pymysql.install_as_MySQLdb()
