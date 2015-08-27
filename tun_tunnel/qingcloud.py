#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Author  :   windpro
E-mail  :   windprog@gmail.com
Date    :   15/8/26
Desc    :   
"""
import time
from qingcloud.iaas import connect_to_zone
import config

TRANSITION_STATE = [
    "creating", "starting", "stopping", "restarting", "suspending", "resuming", "terminating", "recovering", "resetting"
]

CN_SERVER_NAME = 'server_cn'

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


def ensure_keypair():
    """
    确保不会重新创建key
    :return: keypair_id
    """
    keypair_set = conn.describe_key_pairs()['keypair_set']
    for keypair in keypair_set:
        if keypair['pub_key'] in config.MACHINE_PUB_KEY:
            return keypair['keypair_id']
    return conn.create_keypair(keypair_name='tunnel', mode='user', encrypt_method='ssh-rsa',
                               public_key=config.MACHINE_PUB_KEY)['keypair_id']


def ensure_server(server_name=CN_SERVER_NAME, timeout=10):
    """
    确保不会重复创建server
    :return: instance_id
    """
    all_instance_set = conn.describe_instances(
        status=["pending", "running", "stopped", "suspended"]+TRANSITION_STATE)['instance_set']
    for instance in all_instance_set:
        if instance['instance_name'] == server_name:
            if instance['status'] == 'pending' or instance['status'] in TRANSITION_STATE:
                for _ in xrange(timeout):
                    print "等待中"
                    time.sleep(1)
                    pending_ins = conn.describe_instances(instances=[instance['instance_id']])['instance_set']
                    if pending_ins and pending_ins[0]['status'] != 'pending':
                        return instance['instance_id']
                raise Exception('创建instance_name: %s 超时' % server_name)
            elif instance['status'] == 'running':
                # 目标资源正在运行，直接返回
                return instance['instance_id']
            else:
                # 资源需要删除
                conn.terminate_instances(instances=[instance['instance_id']])
    run_ins = conn.run_instances(instance_name="server_cn", image_id='trustysrvx64e', cpu=1, memory=1024,
                                 login_mode="keypair", login_keypair=ensure_keypair())
    if 'instances' not in run_ins or len(run_ins['instances']) == 0:
        raise Exception('创建instance_name: %s 配额不足' % server_name)
    return ensure_server(server_name)


def delete_all_instance_by_server_name(server_name=CN_SERVER_NAME):
    need_delete_list = [
        instance['instance_id'] for instance in conn.describe_instances(
            status=["pending", "running", "stopped", "suspended"]+TRANSITION_STATE,
            instance_name=server_name,
    )['instance_set']]
    if not need_delete_list:
        return
    ret = conn.terminate_instances(instances=need_delete_list)
    if ret.get('ret_code') != 0:
        print 'api访问错误，等待5秒重试'
        time.sleep(5)
        ret = delete_all_instance_by_server_name(server_name)
    return ret


if __name__ == '__main__':
    ensure_server(CN_SERVER_NAME)
