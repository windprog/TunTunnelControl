#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Author  :   windpro
E-mail  :   windprog@gmail.com
Date    :   15/8/26
Desc    :   
"""
from qingcloud.iaas import connect_to_zone
import config

conn = connect_to_zone(
    'gd1',
    config.QC_GD1_KEY_ID,
    config.QC_GD1_ACCESS_KEY,
)


def show_all_image():
    rs = [(item['image_id'], item['image_name']) for item in
          conn.describe_images(zone='gd1', provider='system', limit=200)['image_set']]
    rs.sort()
    return rs

#start
conn.run_instances(image_id='trustysrvx64e', cpu=1, memory=1024, login_mode='passwd', login_passwd='Aaaa8888')
# stop
conn.terminate_instances(instances=['i-efkrp2c9'])
