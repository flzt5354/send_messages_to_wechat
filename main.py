import requests
import json
import os
import time
import re


# 读取配置文件
def rdconfig(filename):
    if (os.path.exists(filename)):
        with open(filename, "r") as f:
            config = json.load(f)
            # print("读取配置文件完成...")
            return config
    else:
        print('初始化配置文件')
        with open(filename, "w") as f:
            appID = input('appID: ')
            appsecret = input('appsecret: ')
            userid = input('userid: ')
            template_id = input('template_id: ')
            token = get_token(appID, appsecret)
            res = {"appID": appID, "appsecret": appsecret, "token": token, "userid": {userid: '1'},
                   "template_id": template_id}
            res1 = json.dumps(res)
            f.write(str(res1))
            f.close()
            return res


# 获取用户列表 并保存在全局变量
g_config = rdconfig('token.json')
g_userID = list(g_config['userid'].keys())  # 用户LIST
g_user_sent_switch = list(g_config['userid'].values())  # 是否需要发送消息的标记，暂时没用
# 获取模板
g_template_id = g_config['template_id']  # 模板ID


def get_token(appID, appsecret):
    url_token = 'https://api.weixin.qq.com/cgi-bin/token?'
    res = requests.get(url=url_token, params={
        "grant_type": 'client_credential',
        'appid': appID,
        'secret': appsecret,
    }).json()
    token = res.get('access_token')
    return token


# 写入配置文件
def wrconfig(new_dict, filename):
    with open(filename, "w") as f:
        json.dump(new_dict, f)
    # print("写入配置文件完成...")


def sendtext(token, userID, text):
    url_msg = 'https://api.weixin.qq.com/cgi-bin/message/custom/send?'
    body = {
        "touser": userID,  # 这里必须是关注公众号测试账号后的用户id
        "msgtype": "text",
        "text": {
            "content": text
        }
    }
    res = requests.post(url=url_msg, params={
        'access_token': token  # 这里是我们上面获取到的token
    }, data=json.dumps(body, ensure_ascii=False).encode('utf-8'))
    return res


def sendmb(token, template_id, userID, text, color, share_url):
    url_msg = 'https://api.weixin.qq.com/cgi-bin/message/template/send?'
    body = {
        "touser": userID,  # 这里必须是关注公众号测试账号后的用户id
        "template_id": template_id,
        "url": share_url,
        "topcolor": color,
        "data": {
            "text": {
                "value": text,
                "color": color
            }
        }
    }
    res = requests.post(url=url_msg, params={
        'access_token': token  # 这里是我们上面获取到的token
    }, data=json.dumps(body, ensure_ascii=False).encode('utf-8'))
    return res


def send(text, g_userID, config, share_url):
    # 发送消息
    # 直接传递用户的userID[i]进来,这里不作发送判断
    res = sendtext(config['token'], g_userID, text)

    if (res.json()['errcode'] == 42001):  # token两小时过期后重新获取
        config['token'] = get_token(config['appID'], config['appsecret'])
        wrconfig(config, 'token.json')
        res = sendtext(config['token'], g_userID, text)

    if (res.json()['errcode'] == 45047):  # 客服消息如果长时间不回复将不能发，这边先换成模板消息
        res = sendmb(config['token'], g_template_id, g_userID,
                     text + '（请及时回复以免消息发送失败）', '#FF0000', share_url)

    return res.json()


def send_to_user(news, share_url):
    # news  传递单独一行的消息
    # sent_data  读取本地数据库，用于比对消息，以及判断用户是否已经发送
    # ------------------------
    # 写入开关, 数据只会在所有消息都跑完，并且有修改的情况下才会在结束时写入数据
    switch = 0
    # -----------------------------------

    # 打开读取本地数据库，
    with open('sent_data.json', 'r') as f:
        sent_data = json.load(f)
    # 判断第一条重要消息是否存在于数据库
    news_exisit = news in sent_data.keys()
    # 本地数据库格式 {news ： {userid : send_record} }
    # { “我是新闻" : {"XXX用户ID":"1"} }
    # send_record "0"表示 没有发送 ”1“ 已经发送
    # ----------------------------------------

    if news_exisit == False:
        # 不存在于数据库
        for userid in range(len(g_userID)):  # 对用户发送消息
            # 因为消息不存在于数据库，所以不作发送判断
            # 直接写入即可
            # send 模块，需要给到用户实际的ID
            # 从全局变量中读取list, 从循环中获取ID
            # news_exisit = news in sent_data.keys()
            code = send(news, g_userID[userid], g_config, share_url)
            if code['errmsg'] == 'ok':  # 发送成功
                # 判断字典是否有用户数据了- 即第二次遍历 userid = 1的情况
                news_exisit = news in sent_data.keys()
                if news_exisit == True:  # 第二次运行，消息已经创建了
                    temp_user_record = {g_userID[userid]: "1"}
                    # 追加更新数据
                    sent_data[news].update(temp_user_record)
                    switch = 1  # 需要写入数据
                else:
                    # 第一次运行直接更新字典
                    sent_data[news] = {g_userID[userid]: "1"}
                    switch = 1  # 需要写入数据
            # 发送失败
            else:
                print(code)  # 打印错误提示
        time.sleep(0.1)

    else:
        # ----------------- 消息存在，对未发送的用户发送-----------------
        for userid in range(len(g_userID)):  # 对用户发送消息
            # 这里情况有两中，一是新用户，二是老用户
            # ------------识别是否新用户-------------
            old_user = g_userID[userid] in sent_data[news].keys()
            # 返回 True  or  False
            # 老用户
            if old_user == True:
                # 提取用户的send_record
                send_record = sent_data[news][g_userID[userid]]
                if send_record == '0':
                    # 消息没有发送，则发送
                    code = send(news, g_userID[userid], g_config, share_url)
                    if code['errmsg'] == 'ok':  # 发送成功
                        # 标记发送成功
                        sent_data[news][g_userID[userid]] = '1'  # 修改数据
                        switch = 1  # 需要写入
                        # print("成功对未发送的用户%s 发送了消息" % g_userID[user])
                        time.sleep(0.1)
            # 这是新用户，直接发送
            else:
                code = send(news, g_userID[userid], g_config, share_url)
                if code['errmsg'] == 'ok':  # 发送成功
                    # 标记发送成功
                    sent_data[news][g_userID[userid]] = '1'  # 修改数据
                    switch = 1  # 需要写入
                    # print("成功对未发送的用户%s 发送了消息" % g_userID[user])
                    time.sleep(0.1)

    # 数据有更改需要写入
    if switch == 1:
        with open('sent_data.json', 'w') as f:
            json.dump(sent_data, f, ensure_ascii=False)
            print("已经写入数据")

def local_data_balance():
    # 动态平衡本地数据的数量，仅保留50条最新的消息，以免程序在长时间运转后影响性能
    # 打开读取数据库，
    with open('sent_data.json', 'r') as f:
        sent_data = json.load(f)
    # 获取本地消息的list
    news_num = list(sent_data.keys())
    l = len(news_num) - 50
    if l >= 1:
        for i in range(l):
            sent_data.pop(news_num[i], None)
        with open('sent_data.json', 'w') as f:
            json.dump(sent_data, f, ensure_ascii=False)
            print("本地数据平衡完毕")
            time.sleep(5)

def get_data():
    # 伪装成浏览器登录，通过设置User_Agent，将其存放到Headers中，网站服务器通过User_Agent进行判断是谁在登录访问该网页
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:83.0) Gecko/20100101 Firefox/83.0"
    }
    url = 'https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=40'
    content = requests.get(url, headers=headers).text

    # 一级数据清洗 先判断是否存在值得关注的消息
    im_sign = re.search('"import":"3"', str(content))

    if im_sign != None:

        # 把JSON转成python 字典格式
        data = json.loads(content)
        data_list = data['data']['list']
        data_len = len(data_list)  # 获取消息的数目

        for i in range(data_len):
            # 获取单独一行消息的内容
            news = str(data['data']['list'][i]['digest'])
            news_url = str(data['data']['list'][i]['shareUrl'])
            # 提取重要等级标记
            im = data['data']['list'][i]['import']
            if im >= '3':  # 只有3级以上才是需要的
                # -----------发送消息-------------------
                send_to_user(news, news_url)


s = "程序正常运行中 - 正在努力爬取同花顺的财经消息"
while True:
    # 控制台美化 - 打字机模式输出 字符串
    os.system('cls')
    for i in range(len(s)):
        print(s[0:i])
        time.sleep(0.1)
        os.system('cls')
    print(s)
    # 获取时间
    h =int(time.strftime('%H'))

    if h >= 7 and i<=23:
        get_data()
        time.sleep(5)
    else: # 深夜免打扰模式
        sl = (6 - h) * 3600
        if sl == 0:
            m = int(time.strftime('%M'))
            sl = (61 - m) * 60
        # 每天进行一次数据清理
        local_data_balance()
        print("深夜了，已经过了晚上11点，程序已经休眠，将于早上7点重新启动")
        time.sleep(sl)

# 发送模板消息
# sendmb(token,template_id,userID,'程序错误，请及时回复','#FF0000')
