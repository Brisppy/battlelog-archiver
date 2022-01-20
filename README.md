# battlelog-archiver

```
A script for archiving pc bf4 battlelog player data, along with battle reports.
REQUIRES:
  aiohttp (python3 -m pip install aiohttp)
NOTES:
  Ensure you have access to all user profile data (battle reports etc) otherwise they cannot be saved.
  All files will be placed in the current directory.
ARGUMENTS:
  1: Profile name - e.g 'Brisppy'
  2: Path to cookie file - e.g 'C:\\Users\\Brisppy\\cookie.txt' - Fetch using 'Get cookies.txt' Chrome extension.
      - Use 2 slashes for Windows paths.
```