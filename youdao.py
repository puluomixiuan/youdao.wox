import http.client
import json
import urllib
import webbrowser
import time
import hashlib
import base64
import random
import string

from wox import Wox

QUERY_URL = 'http://dict.youdao.com/search?q='
SUGGEST_URL = 'https://dict.youdao.com/suggest'

# API配置 - 如果需要使用自己的API key，请在这里配置
APP_KEY = ""  # 你的有道翻译appKey
APP_SECRET = ""  # 你的有道翻译appSecret

# 缓存和频率控制
CACHE = {}  # 翻译结果缓存
SUGGEST_CACHE = {}  # 建议结果缓存
LAST_REQUEST_TIME = 0  # 上次请求时间
MIN_REQUEST_INTERVAL = 0.5  # 最小请求间隔（秒）
EMPTY_RESULT = {
    'Title': 'Start to translate between Chinese and English',
    'SubTitle': 'Powered by youdao api, Python3.x only.',
    'IcoPath': 'Img\\youdao.ico'
}
SERVER_DOWN = {
    'Title': '网易在线翻译服务暂不可用',
    'SubTitle': '请待服务恢复后再试',
    'IcoPath': 'Img\\youdao.ico'
}
ERROR_INFO = {
    "101": "缺少必填的参数，出现这个情况还可能是et的值和实际加密方式不对应",
    "102": "不支持的语言类型",
    "103": "翻译文本过长",
    "104": "不支持的API类型",
    "105": "不支持的签名类型",
    "106": "不支持的响应类型",
    "107": "不支持的传输加密类型",
    "108": "appKey无效，注册账号，登录后台创建应用和实例并完成绑定，可获得应用ID和密钥等信息，其中应用ID就是appKey（注意不是应用密钥）",
    "109": "batchLog格式不正确",
    "110": "无相关服务的有效实例",
    "111": "开发者账号无效",
    "113": "q不能为空",
    "201": "解密失败，可能为DES,BASE64,URLDecode的错误",
    "202": "签名检验失败",
    "203": "访问IP地址不在可访问IP列表",
    "205": "请求的接口与选择的接入方式不一致",
    "301": "辞典查询失败",
    "302": "翻译查询失败",
    "303": "服务端的其它异常",
    "401": "账户已经欠费",
    "411": "访问频率受限,请稍后访问",
    "2005": "ext参数不对",
    "2006": "不支持的voice",
}


class Main(Wox):

    def query(self, param):
        result = []
        q = param.strip()
        if not q:
            return [EMPTY_RESULT]

        # 智能建议逻辑：短输入或看起来像部分单词时显示建议
        should_show_suggestions = (
            len(q) < 5 or  # 少于5个字符
            (len(q) < 8 and q.endswith('ing')) or  # 以ing结尾的短词
            (len(q) < 8 and q.endswith('ed')) or   # 以ed结尾的短词
            q.count(' ') == 0 and len(q) < 6  # 无空格的短词
        )
        
        if should_show_suggestions:
            suggestions = self.get_suggestions(q)
            if suggestions and suggestions.get('result', {}).get('code') == 200:
                suggest_data = suggestions.get('data', {}).get('entries', [])
                for item in suggest_data[:5]:  # 最多显示5个建议
                    result.append({
                        'Title':  f"建议: {item.get('explain', '')}",
                        'SubTitle': item.get('entry', ''),
                        'IcoPath': 'Img\\youdao.ico',
                        'JsonRPCAction': {
                            'method': 'open_url',
                            'parameters': [item.get('entry', ''), QUERY_URL]
                        }
                    })
                if result:
                    return result

        # 检查缓存
        if q in CACHE:
            cached_result = CACHE[q]
            if time.time() - cached_result['timestamp'] < 300:  # 缓存5分钟
                return cached_result['data']

        # 频率控制
        current_time = time.time()
        if current_time - LAST_REQUEST_TIME < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - (current_time - LAST_REQUEST_TIME))

        # 优先尝试使用API key，如果没有配置则使用演示API
        if APP_KEY and APP_SECRET:
            response = self.yd_api_with_key(q)
        else:
            response = self.yd_api(q)
        if not response:
            # 如果翻译失败，尝试显示建议
            suggestions = self.get_suggestions(q)
            if suggestions and suggestions.get('result', {}).get('code') == 200:
                suggest_data = suggestions.get('data', {}).get('entries', [])
                for item in suggest_data[:3]:  # 显示3个建议作为备选
                    result.append({
                        'Title': item.get('entry', ''),
                        'SubTitle': f"建议: {item.get('explain', '')}",
                        'IcoPath': 'Img\\youdao.ico',
                        'JsonRPCAction': {
                            'method': 'open_url',
                            'parameters': [item.get('entry', ''), QUERY_URL]
                        }
                    })
                if result:
                    return result
            
            return [{
                'Title': '网络请求失败',
                'SubTitle': '请检查网络连接是否正常',
                'IcoPath': 'Img\\youdao.ico'
            }]
        errCode = response.get('errorCode', '')
        if not errCode:
            return [SERVER_DOWN]

        if errCode != '0':
            # 特殊处理401错误
            if errCode == '401':
                return [{
                    'Title': 'API使用量超限',
                    'SubTitle': '请稍后再试或检查API配额',
                    'IcoPath': 'Img\\youdao.ico'
                }]
            return [{
                'Title': ERROR_INFO.get(errCode, '访问频率受限,请稍后访问'),
                'SubTitle': 'errorCode=%s' % errCode,
                'IcoPath': 'Img\\youdao.ico'
            }]

        tSpeakUrl = response.get('tSpeakUrl', '')
        translation = response.get('translation', [])
        basic = response.get('basic', {})
        web = response.get('web', [])

        if translation:
            result.append({
                'Title': translation[0],
                'SubTitle': '有道翻译',
                'IcoPath': 'Img\\youdao.ico',
                'JsonRPCAction': {
                    'method': 'open_url',
                    'parameters': [q, QUERY_URL]
                }
            })

        if tSpeakUrl:
            result.append({
                'Title': '获取发音',
                'SubTitle': '点击可跳转 - 有道翻译',
                'IcoPath': 'Img\\youdao.ico',
                'JsonRPCAction': {
                    'method': 'open_url',
                    'parameters': [tSpeakUrl]
                }
            })
        if basic:
            for i in basic['explains']:
                result.append({
                    'Title': i,
                    'SubTitle': '{} - 基本词典'.format(response.get('query', '')),
                    'IcoPath': 'Img\\youdao.ico',
                    'JsonRPCAction': {
                        'method': 'open_url',
                        'parameters': [q, QUERY_URL]
                    }
                })
        if web:
            for i in web:
                result.append({
                    'Title': ','.join(i['value']),
                    'SubTitle': '{} - 网络释义'.format(i['key']),
                    'IcoPath': 'Img\\youdao.ico',
                    'JsonRPCAction': {
                        'method': 'open_url',
                        'parameters': [q, QUERY_URL]
                    }
                })
        
        # 缓存结果
        CACHE[q] = {
            'data': result,
            'timestamp': time.time()
        }
        
        return result

    def open_url(self, query, url=None):
        if url:
            webbrowser.open(url + query)
        else:
            webbrowser.open(query)

    @staticmethod
    def yd_api(q, retry_count=3):
        global LAST_REQUEST_TIME
        
        # 更新最后请求时间
        LAST_REQUEST_TIME = time.time()
        
        payload = "q={}&from=Auto&to=Auto".format(urllib.parse.quote(q))
        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36',
            'Cache-Control': "no-cache"
        }
        
        conn = None
        for attempt in range(retry_count):
            try:
                conn = http.client.HTTPSConnection("aidemo.youdao.com", timeout=10)
                conn.request("POST", "/trans", payload, headers)
                res = conn.getresponse()
                
                if res.code == 200:
                    response_data = json.loads(res.read().decode("utf-8"))
                    return response_data
                elif res.code == 429:  # 频率限制
                    if attempt < retry_count - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)  # 指数退避
                        time.sleep(wait_time)
                        continue
                else:
                    if attempt < retry_count - 1:
                        time.sleep(1)
                        continue
                        
            except (http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError) as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
            finally:
                if conn:
                    conn.close()
                    conn = None
        
        return None

    @staticmethod
    def yd_api_with_key(q, retry_count=3):
        """使用正式API key的翻译方法（可选）"""
        global LAST_REQUEST_TIME
        
        if not APP_KEY or not APP_SECRET:
            return None
            
        LAST_REQUEST_TIME = time.time()
        
        # 生成签名
        salt = str(int(time.time() * 1000))
        sign_str = APP_KEY + q + salt + APP_SECRET
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        
        payload = {
            'q': q,
            'from': 'auto',
            'to': 'auto',
            'appKey': APP_KEY,
            'salt': salt,
            'sign': sign
        }
        
        payload_str = urllib.parse.urlencode(payload)
        headers = {
            'Content-Type': "application/x-www-form-urlencoded",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        conn = None
        for attempt in range(retry_count):
            try:
                conn = http.client.HTTPSConnection("openapi.youdao.com", timeout=10)
                conn.request("POST", "/api", payload_str, headers)
                res = conn.getresponse()
                
                if res.code == 200:
                    response_data = json.loads(res.read().decode("utf-8"))
                    return response_data
                elif res.code == 429:
                    if attempt < retry_count - 1:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue
                else:
                    if attempt < retry_count - 1:
                        time.sleep(1)
                        continue
                        
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
            finally:
                if conn:
                    conn.close()
                    conn = None
        
        return None

    @staticmethod
    def detect_language(text):
        """检测文本语言"""
        # 简单的语言检测逻辑
        chinese_chars = 0
        english_chars = 0
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
                chinese_chars += 1
            elif char.isalpha():  # 英文字母
                english_chars += 1
        
        # 如果中文字符占多数，返回中文
        if chinese_chars > english_chars:
            return 'zh'
        else:
            return 'en'
    
    @staticmethod
    def get_suggestions_for_language(q, lang, num=5):
        """根据指定语言获取建议"""
        global LAST_REQUEST_TIME
        
        # 检查建议缓存（包含语言信息）
        cache_key = f"{q}_{lang}"
        if cache_key in SUGGEST_CACHE:
            cached_result = SUGGEST_CACHE[cache_key]
            if time.time() - cached_result['timestamp'] < 60:  # 建议缓存1分钟
                return cached_result['data']
        
        # 频率控制
        current_time = time.time()
        if current_time - LAST_REQUEST_TIME < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - (current_time - LAST_REQUEST_TIME))
        
        LAST_REQUEST_TIME = time.time()
        
        # 构建请求URL
        params = {
            'num': num,
            'ver': '3.0',
            'doctype': 'json',
            'cache': 'false',
            'le': lang,
            'q': q
        }
        
        url_params = urllib.parse.urlencode(params)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        }
        
        conn = None
        try:
            conn = http.client.HTTPSConnection("dict.youdao.com", timeout=5)
            conn.request("GET", f"/suggest?{url_params}", headers=headers)
            res = conn.getresponse()
            
            if res.code == 200:
                response_data = json.loads(res.read().decode("utf-8"))
                
                # 缓存结果
                SUGGEST_CACHE[cache_key] = {
                    'data': response_data,
                    'timestamp': time.time()
                }
                
                return response_data
                
        except Exception as e:
            pass
        finally:
            if conn:
                conn.close()
        
        return None

    @staticmethod
    def get_suggestions(q, num=5):
        """获取输入建议"""
        # 自动检测语言
        detected_lang = Main.detect_language(q)
        
        # 尝试获取建议
        suggestions = Main.get_suggestions_for_language(q, detected_lang, num)
        
        # 如果检测为中文但建议失败，尝试英文建议
        if not suggestions and detected_lang == 'zh':
            suggestions = Main.get_suggestions_for_language(q, 'en', num)
        
        return suggestions

    def __get_proxies(self):
        proxies = {}
        if self.proxy and self.proxy.get("enabled") and self.proxy.get("server"):
            proxies["http"] = "http://{}:{}".format(self.proxy.get("server"), self.proxy.get("port"))
            proxies["https"] = "http://{}:{}".format(self.proxy.get("server"), self.proxy.get("port"))
        return proxies


if __name__ == '__main__':
    Main()
