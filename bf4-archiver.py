#!/usr/bin/python
# A script for archiving pc bf4 battlelog player data, along with battle reports.
# REQUIRES:
#   aiohttp (python3 -m pip install aiohttp)
# NOTES:
#   Ensure you have access to all user profile data (battle reports etc) otherwise they cannot be saved.
#   All files will be placed in the current directory.
# ARGUMENTS:
#   1: Profile name - e.g 'Brisppy'
#   2: Path to cookie file - e.g 'C:\\Users\\Brisppy\\cookie.txt' - Fetch using 'Get cookies.txt' Chrome extension.
#       - Use 2 slashes for Windows paths.

import os
import sys
import math
import json
import time
import numpy
import aiohttp
import asyncio
import requests
from pathlib import Path
import http.cookiejar as cookielib


def battlelogApiFetch(endpoint, headers, cookie):
    url = 'https://battlelog.battlefield.com/bf4' + endpoint
    while True:
        try:
            r = requests.get(url, headers=headers, cookies=cookie)
            if r.status_code == 504:
                time.sleep(5)
                continue
            elif r.status_code == 403:
                print('ERROR: Error 403 Forbidden received. Most likely IP blocked.')
                sys.exit(1)
            else:
                break
        except BaseException as e:
            print('ERROR: Error accessing battlelog API.')
            print('ERROR:', e)
            sys.exit(1)
    try:
        return json.loads(r.text)
    except:
        return {}


# Function for fetching battlereports. A symbol is printed for each response:
#   o = success
#   . = bad response (retry after 5s)
#   x = failed
#   X = failed due to 403 (retry after 10m)
async def battlelogRetrieveReport(session, url):
    attempt = 0
    while True:
        attempt += 1
        try:
            async with session.get(url) as resp:
                assert resp.status == 200
                report = await resp.json()
                if report and await resp.text() != 'null':
                    sys.stdout.write("o")
                    sys.stdout.flush()
                    return report
                elif attempt >= 6:
                    sys.stdout.write("x")
                    sys.stdout.flush()
                    return {}
                else:
                    # No data returned, try again after 5s - possibly rate limited
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    time.sleep(3)
                    continue
        except AssertionError:
            sys.stdout.write("X")
            sys.stdout.flush()
            time.sleep(600)
            continue
        except aiohttp.client_exceptions.ClientOSError:
            time.sleep(10)
            continue

async def main():
    # Grab and store cookie data
    cookie = cookielib.MozillaCookieJar(str(Path(sys.argv[2])))
    cookie.load()
    # Store profile name
    profile_name = sys.argv[1]
    # Fetch profile data
    headers = {'X-AjaxNavigation': '1', 'X-Requested-With': 'XMLHttpRequest'}
    print('INFO: Fetching profile data...', end='\r')
    profile_data = battlelogApiFetch('/user/' + profile_name + '/', headers, cookie)
    print('INFO: Fetching profile data... Done')
    profile_id = profile_data['context']['activitystream'][0]['persona']['personaId']
    user_id = profile_data['context']['activitystream'][0]['persona']['userId']
    club_id = profile_data['context']['profileCommon']['club']['id']
    # Fetch active club data
    print('INFO: Fetching active club data...', end='\r')
    club_data = battlelogApiFetch('/platoons/view/' + club_id + '/', headers, cookie)
    print('INFO: Fetching active club data... Done')
    # Fetch other stats
    # Weapons
    print('INFO: Fetching weapon stats...', end='\r')
    weapon_stats = battlelogApiFetch('/warsawWeaponsPopulateStats/'+ profile_id + '/1/stats/', headers, cookie)
    print('INFO: Fetching weapon stats... Done')
    # Vehicles
    print('INFO: Fetching vehicle stats...', end='\r')
    vehicle_stats = battlelogApiFetch('/warsawvehiclesPopulateStats/'+ profile_id + '/1/stats/', headers, cookie)
    print('INFO: Fetching vehicle stats... Done')
    # Detailed
    print('INFO: Fetching detailed stats...', end='\r')
    detailed_stats = battlelogApiFetch('/warsawdetailedstatspopulate/'+ profile_id + '/1/stats/', headers, cookie)
    print('INFO: Fetching detailed stats... Done')
    # Assignments
    print('INFO: Fetching assignment stats...', end='\r')
    assignment_stats = battlelogApiFetch('/soldier/missionsPopulateStats/'+ profile_name + '/' + profile_id + '/' + user_id + '/1/', headers, cookie)
    print('INFO: Fetching assignment stats... Done')
    # Awards
    print('INFO: Fetching award stats...', end='\r')
    award_stats = battlelogApiFetch('/warsawawardspopulate/'+ profile_id + '/1/stats/', headers, cookie)
    print('INFO: Fetching award stats... Done')
    # Generate list of battlereports
    print('INFO: Fetching reports, this may take a while...', end='\r')
    report_list = []
    # Fetch initial report list
    try:
        report_list.extend(battlelogApiFetch('/warsawbattlereportspopulate/' + profile_id + '/2048/1/', headers, cookie)['data']['gameReports'][:])
    except KeyError:
        print('ERROR: Battle reports probably are hidden by user (See ' + 'https://battlelog.battlefield.com/bf4/soldier/' + profile_name + '/battlereports/' +  profile_id + '/pc/' + ').')
        sys.exit(1)
    noDataReturned = 0
    while True:
        # Fetch next x number of reports, using the most recent report
        reports = battlelogApiFetch('/warsawbattlereportspopulatemore/' + profile_id + '/2048/1/' + str(report_list[-1]['createdAt']), headers, cookie)
        # Break loop when no more reports can be returned.
        if not reports['data']['gameReports'] and noDataReturned >= 5:
            break
        elif not reports['data']['gameReports']:
            noDataReturned += 1
            continue
        else:
            noDataReturned = 0
            report_list.extend(reports['data']['gameReports'][:])
            print('INFO: Fetching reports, this may take a while... ' + str(len(report_list)) + ' found.', end='\r')
            continue
    print('INFO: Fetching reports, this may take a while...                                                 ', end='\r')
    print('INFO: Fetching reports, this may take a while... Done')
    print('INFO: Total reports:', len(report_list))
    # Fetch data for individual reports
    print('INFO: Now fetching individual reports, this can take a LONG time...')
    battlelog_reports = []
    cookies = {}
    for each in cookie:
        cookies[each.name] = each.value
    # First the list of reports has to be split into smaller chunks as I was encountering issues with rate limiting when using a single session.
    report_list = numpy.array_split(report_list, math.ceil(len(report_list)/20))
    timeout = aiohttp.ClientTimeout(total=6000)
    for report_list_chunk in range(len(report_list)):
        async with aiohttp.ClientSession(timeout=timeout, headers=headers, cookies=cookies) as session:
            tasks = []
            for report_number in range(len(report_list[report_list_chunk])):
                url = 'https://battlelog.battlefield.com/bf4/battlereport/loadgeneralreport/' + str(report_list[report_list_chunk][report_number]['gameReportId']) + '/1/' + profile_id + '/'
                tasks.append(asyncio.ensure_future(battlelogRetrieveReport(session, url)))
            reports = await asyncio.gather(*tasks)
            for report in reports:
                if report:
                    battlelog_reports.append(report)
                else:
                    continue
    print('\nINFO: Done fetching reports.')
    # Write data to the current directory
    print('INFO: Writing data to disk...', end='\r')
    while True:
        try:
            stats_directory = Path(os.getcwd(), 'bf4-battlelog-archive', profile_name)
            os.makedirs(Path(stats_directory, 'reports'), exist_ok=True)
            with open(Path(stats_directory, 'profile_data.json'), 'w') as f: f.write(str(profile_data))
            with open(Path(stats_directory, 'club_data.json'), 'w') as f: f.write(str(club_data))
            with open(Path(stats_directory, 'weapon_stats.json'), 'w') as f: f.write(str(weapon_stats))
            with open(Path(stats_directory, 'vehicle_stats.json'), 'w') as f: f.write(str(vehicle_stats))
            with open(Path(stats_directory, 'detailed_stats.json'), 'w') as f: f.write(str(detailed_stats))
            with open(Path(stats_directory, 'assignment_stats.json'), 'w') as f: f.write(str(assignment_stats))
            with open(Path(stats_directory, 'award_stats.json'), 'w') as f: f.write(str(award_stats))
            with open(Path(stats_directory, 'report_list.json'), 'w') as f: f.write(str(report_list))
            for report_number in range(len(battlelog_reports)):
                with open(Path(stats_directory, 'reports', str(battlelog_reports[report_number]['id']) + '.json'), 'w') as f: f.write(str(battlelog_reports[report_number]))
            print('INFO: Writing data to disk... Done')
            break
        except BaseException as e:
            print('ERROR: Error writing to disk.')
            print('ERROR:', e)
            sys.exit(1)


if __name__=='__main__':
    asyncio.run(main())
