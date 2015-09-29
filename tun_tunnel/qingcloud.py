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

INSTANCE_TRANSITION_STATE = [
    "creating", "starting", "stopping", "restarting", "suspending", "resuming", "terminating", "recovering", "resetting"
]
IPS_TRANSITION_STATE = [
    "associating", "dissociating", "suspending", "resuming", "releasing"
]

STAND_BY_STATE = [
    "running",  # 主机准备好
    "available",  # ip准备好
]

response_resources_name = [
    "instance_set",  # 主机键值
    "eip_set",  # ip键值
]

CN_SERVER_NAME = 'server_cn'
CN_IP_NAME = 'ip_cn'

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


class TimeOutException(Exception):
    pass


def wait_call(callback, timeout=10, *args, **kwargs):
    for _ in xrange(timeout):
        print "等待中"
        time.sleep(1)
        pending_ins = callback(*args, **kwargs)['instance_set']
        if pending_ins and pending_ins[0] and 'status' in pending_ins[0] and pending_ins[0]['status'] in STAND_BY_STATE:
            return True
    raise TimeOutException


def wait_instance(instance_id, timeout=10):
    return wait_call(conn.describe_instances, timeout=timeout, instances=[instance_id])


def wait_eip(eip_id, timeout=10):
    return wait_call(conn.describe_eips, timeout=timeout, instances=[eip_id])


def ensure_server(server_name=CN_SERVER_NAME, timeout=10):
    """
    确保不会重复创建server
    :return: instance_id
    """
    all_instance_set = conn.describe_instances(
        search_word=server_name,
        status=["pending", "running", "stopped", "suspended"] + INSTANCE_TRANSITION_STATE)['instance_set']
    for instance in all_instance_set:
        if instance['status'] in INSTANCE_TRANSITION_STATE + ['pending']:
            try:
                if wait_instance(instance['instance_id'], timeout=timeout):
                    return instance['instance_id']
            except TimeOutException:
                Exception('创建instance_name: %s 超时' % server_name)
        elif instance['status'] == 'running':
            # 目标资源正在运行，直接返回
            result_id = instance['instance_id']
            # 资源需要删除
            conn.terminate_instances(instances=list(set(
                [tins['instance_id'] for tins in all_instance_set]) - {result_id}))
            return result_id
        else:
            # 资源需要删除
            conn.terminate_instances(instances=[instance['instance_id']])
    run_ins = conn.run_instances(instance_name="server_cn", image_id='trustysrvx64e', cpu=1, memory=1024,
                                 login_mode="keypair", login_keypair=ensure_keypair(), vxnets=['vxnet-0'])
    if 'instances' not in run_ins or len(run_ins['instances']) == 0:
        raise Exception('创建instance_name: %s 配额不足' % server_name)
    return ensure_server(server_name)


def delete_instance_by_server_name(server_name=CN_SERVER_NAME):
    need_delete_list = [
        instance['instance_id'] for instance in conn.describe_instances(
            status=["pending", "running", "stopped", "suspended"] + INSTANCE_TRANSITION_STATE,
            search_word=server_name,
        )['instance_set']]
    if not need_delete_list:
        return
    ret = conn.terminate_instances(instances=need_delete_list)
    if ret.get('ret_code') != 0:
        print 'api访问错误，等待5秒重试'
        time.sleep(5)
        ret = delete_instance_by_server_name(server_name)
    return ret


def ensure_ip(ip_name=CN_IP_NAME, timeout=10):
    eip_set = conn.describe_eips(
        search_word=ip_name,
        status=["pending", "available", "suspended"] + IPS_TRANSITION_STATE)['eip_set']
    for eip in eip_set:
        if eip['status'] in ["pending"] + IPS_TRANSITION_STATE:
            if wait_eip(eip['eip_id'], timeout=timeout):
                return eip['eip_id']
        elif eip['status'] == "available":
            # 目标资源正在运行，直接返回
            result_id = eip['eip_id']
            # 资源需要删除
            conn.release_eips(eips=list(set(
                [teip['eip_id'] for teip in eip_set]) - {result_id}))
            return result_id
        else:
            conn.release_eips(eips=[eip['eip_id']])
    run_ips = conn.allocate_eips(bandwidth=15, billing_mode='traffic', eip_name=ip_name)
    if 'eips' not in run_ips or len(run_ips['eips']) == 0:
        raise Exception('创建instance_name: %s 配额不足' % ip_name)
    return ensure_ip(ip_name)


def delete_ip_by_ip_name(ip_name=CN_IP_NAME):
    eip_set = conn.describe_eips(
        status=["pending", "available", "suspended"] + IPS_TRANSITION_STATE)['eip_set']
    if not eip_set:
        return
    for _ in xrange(3):
        dis_connect_info = conn.dissociate_eips(eips=[eip['eip_id'] for eip in eip_set])
        if dis_connect_info['ret_code'] == 0:
            break
    ret = conn.release_eips(eips=[eip['eip_id'] for eip in eip_set])
    if ret.get('ret_code') != 0:
        print 'api访问错误，等待5秒重试'
        time.sleep(5)
        ret = delete_ip_by_ip_name(ip_name)
    return ret


def bind_ip_to_server(eip_id, instance_id):
    return conn.associate_eip(eip_id, instance_id)


def get_server():
    instance_id = ensure_server()
    ip_id = ensure_ip()
    bind_info = bind_ip_to_server(ip_id, instance_id)
    ip_info = conn.describe_eips(eips=[ip_id])
    assert ip_info['eip_set']
    return ip_info['eip_set'][0]['eip_addr']

def stop_server():
    delete_instance_by_server_name()
    return delete_ip_by_ip_name()


if __name__ == '__main__':
    # print get_server()
    # time.sleep(10)
    print stop_server()
