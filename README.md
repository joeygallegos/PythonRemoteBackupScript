# Python Remote Backup Script
Python script to SSH into servers and extract data backups locally

### Backup Writing Process
Backups should be created on the remote server via whichever process and then the file should be given permission to the backup user so that other users on the server do not have access to tamper or delete files.

This script should authenticate with the remote server using a specific pair of credentials used to access only the backup directory following least privilege.