"""
Bilibili API 模块
提供视频列表获取、字幕提取等功能，支持 WBI 签名验证
"""

from functools import reduce
from hashlib import md5
import urllib.parse
import time
import requests
from typing import Dict, List, Optional


# WBI 签名所需的混淆表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]


class BilibiliAPI:
    """Bilibili API 封装类"""

    def __init__(self, cookies: Dict[str, str]):
        """
        初始化 Bilibili API 客户端

        Args:
            cookies: Bilibili 登录 cookies 字典
        """
        self.cookies = cookies
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com'
        }
        self._img_key = None
        self._sub_key = None

    def _get_mixin_key(self, orig: str) -> str:
        """打乱 img_key 和 sub_key 的字符顺序"""
        return reduce(lambda s, i: s + orig[i], MIXIN_KEY_ENC_TAB, '')[:32]

    def _enc_wbi(self, params: dict, img_key: str, sub_key: str) -> dict:
        """为请求参数进行 WBI 签名"""
        mixin_key = self._get_mixin_key(img_key + sub_key)
        curr_time = round(time.time())
        params['wts'] = curr_time
        params = dict(sorted(params.items()))

        # 过滤特殊字符
        params = {
            k: ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
            for k, v in params.items()
        }

        query = urllib.parse.urlencode(params)
        wbi_sign = md5((query + mixin_key).encode()).hexdigest()
        params['w_rid'] = wbi_sign
        return params

    def _get_wbi_keys(self) -> tuple:
        """获取最新的 WBI keys"""
        if self._img_key and self._sub_key:
            return self._img_key, self._sub_key

        resp = requests.get(
            'https://api.bilibili.com/x/web-interface/nav',
            cookies=self.cookies,
            headers=self.headers
        )
        resp_data = resp.json()

        if resp_data['code'] == 0:
            img_url = resp_data['data']['wbi_img']['img_url']
            sub_url = resp_data['data']['wbi_img']['sub_url']

            self._img_key = img_url.rsplit('/', 1)[1].split('.')[0]
            self._sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]

            return self._img_key, self._sub_key
        else:
            raise Exception(f"获取 WBI keys 失败: {resp_data}")

    def get_user_videos(self, uid: int = 285286947, page_size: int = 10) -> List[Dict]:
        """
        获取指定 UP 主的视频列表

        Args:
            uid: UP 主的 UID，默认为橘鸦
            page_size: 获取数量

        Returns:
            视频列表，每个元素包含 bvid, title, created 等字段
        """
        img_key, sub_key = self._get_wbi_keys()

        params = {
            'mid': uid,
            'ps': page_size,
            'pn': 1,
            'order': 'pubdate'
        }

        signed_params = self._enc_wbi(params, img_key, sub_key)

        url = 'https://api.bilibili.com/x/space/wbi/arc/search'
        response = requests.get(url, params=signed_params, cookies=self.cookies, headers=self.headers)
        data = response.json()

        if data.get('code') == 0:
            return data['data']['list']['vlist']
        else:
            raise Exception(f"获取视频列表失败: {data.get('message')}")

    def get_video_info(self, bvid: str) -> Dict:
        """
        获取视频详细信息

        Args:
            bvid: 视频的 BV 号

        Returns:
            视频信息字典，包含 cid, title 等
        """
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        response = requests.get(url, cookies=self.cookies, headers=self.headers)
        data = response.json()

        if data.get('code') == 0:
            return data['data']
        else:
            raise Exception(f"获取视频信息失败: {data.get('message')}")

    def get_subtitle(self, bvid: str) -> Optional[List[Dict]]:
        """
        获取视频字幕

        Args:
            bvid: 视频的 BV 号

        Returns:
            字幕列表，每个元素包含 from, to, content 字段；如果没有字幕返回 None
        """
        # 先获取视频信息得到 cid
        video_info = self.get_video_info(bvid)
        cid = video_info['cid']

        # 获取字幕信息（使用正确的 API endpoint）
        subtitle_url = f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}"
        sub_resp = requests.get(subtitle_url, cookies=self.cookies, headers=self.headers)
        sub_data = sub_resp.json()

        if sub_data.get('code') != 0:
            raise Exception(f"获取字幕失败: {sub_data.get('message')}")

        subtitles = sub_data['data'].get('subtitle', {}).get('subtitles', [])

        if not subtitles:
            return None

        # 下载字幕内容
        subtitle_url = subtitles[0]['subtitle_url']
        if not subtitle_url.startswith('http'):
            subtitle_url = 'https:' + subtitle_url

        sub_content_resp = requests.get(subtitle_url)
        sub_content = sub_content_resp.json()

        return sub_content['body']

    def get_video_comments(self, bvid: str, page_num: int = 1, page_size: int = 20, 
                           sort: int = 0, no_hot: bool = False) -> Dict:
        """
        获取视频评论列表

        Args:
            bvid: 视频的 BV 号
            page_num: 页码，默认为1
            page_size: 每页评论数，默认为20，最大20
            sort: 排序方式，0:按时间(默认)，1:按点赞数，2:按回复数
            no_hot: 是否不显示热评，默认False(显示热评)

        Returns:
            评论数据字典，包含评论列表、页信息、热评等
        """
        # 先获取视频信息得到 aid (oid)
        video_info = self.get_video_info(bvid)
        oid = video_info['aid']  # 使用 aid 作为 oid
        
        # 构建请求参数
        params = {
            'type': 1,  # 视频评论类型
            'oid': oid,
            'sort': sort,
            'ps': min(page_size, 20),  # 限制最大20
            'pn': page_num,
            'nohot': 1 if no_hot else 0
        }
        
        url = 'https://api.bilibili.com/x/v2/reply'
        response = requests.get(url, params=params, cookies=self.cookies, headers=self.headers)
        data = response.json()
        
        if data.get('code') == 0:
            return data['data']
        else:
            error_msg = data.get('message', '未知错误')
            raise Exception(f"获取评论失败: {error_msg}")

    def get_top_comment(self, bvid: str) -> Optional[Dict]:
        """
        获取视频置顶评论基本信息

        Args:
            bvid: 视频的 BV 号

        Returns:
            置顶评论信息字典，如果没有置顶评论返回 None
            包含字段:
            - rpid: 评论ID
            - author: 作者名
            - content: 评论内容
            - likes: 点赞数
            - ctime: 发布时间戳
            - formatted_time: 格式化时间字符串
            - is_owner: 是否为UP主
            - source: 数据来源
        """
        try:
            # 尝试多种参数组合来获取置顶评论
            param_combinations = [
                {"sort": 1, "no_hot": False, "page_size": 30},
                {"sort": 1, "no_hot": False, "page_size": 50},
                {"sort": 0, "no_hot": False, "page_size": 30},
            ]

            for params in param_combinations:
                try:
                    comments_data = self.get_video_comments(bvid, page_num=1, **params)

                    if not comments_data:
                        continue

                    # 检查 upper.top
                    upper = comments_data.get('upper', {})
                    if upper and upper.get('top'):
                        return self._extract_comment_info(upper['top'], "upper.top")

                    # 检查 top_replies
                    top_replies = comments_data.get('top_replies', [])
                    if top_replies:
                        return self._extract_comment_info(top_replies[0], "top_replies")

                except Exception:
                    continue

            return None

        except Exception as e:
            # 如果获取失败，记录错误但不抛出异常
            print(f"获取置顶评论失败: {e}")
            return None

    def get_uploader_comments(self, bvid: str, max_pages: int = 5) -> List[Dict]:
        """
        获取UP主的所有评论

        Args:
            bvid: 视频的 BV 号
            max_pages: 最大搜索页数，默认5页

        Returns:
            UP主评论列表，包含字段与 get_top_comment 相同，额外包含 type 字段
        """
        try:
            # 获取视频信息得到UP主UID
            video_info = self.get_video_info(bvid)
            if not video_info:
                return []

            up_mid = video_info.get('owner', {}).get('mid')
            if not up_mid:
                return []

            up_comments = []
            seen_rpids = set()

            # 按时间排序查找，逐页搜索
            for page in range(1, max_pages + 1):
                try:
                    comments_data = self.get_video_comments(
                        bvid=bvid,
                        page_num=page,
                        page_size=30,
                        sort=0,
                        no_hot=True
                    )

                    if not comments_data:
                        break

                    replies = comments_data.get('replies', [])
                    if not replies:
                        break

                    for reply in replies:
                        if not reply:
                            continue

                        rpid = reply.get('rpid')
                        if rpid in seen_rpids:
                            continue

                        if str(reply.get('mid', '')) == str(up_mid):
                            comment_info = self._extract_comment_info(reply, f"第{page}页")
                            if comment_info:
                                comment_info['type'] = 'uploader_comment'
                                up_comments.append(comment_info)
                                seen_rpids.add(rpid)

                except Exception:
                    continue

            return up_comments

        except Exception as e:
            print(f"获取UP主评论失败: {e}")
            return []

    def get_all_uploader_related_comments(self, bvid: str) -> List[Dict]:
        """
        获取所有与UP主相关的评论（置顶评论 + UP主评论）

        Args:
            bvid: 视频的 BV 号

        Returns:
            所有UP主相关评论列表，按时间排序
            每个评论包含 type 字段: 'pinned' 或 'uploader_comment'
        """
        try:
            all_comments = []
            seen_rpids = set()

            # 获取置顶评论
            pinned_comment = self.get_top_comment(bvid)
            if pinned_comment:
                pinned_comment['type'] = 'pinned'
                all_comments.append(pinned_comment)
                seen_rpids.add(pinned_comment['rpid'])

            # 获取UP主评论
            uploader_comments = self.get_uploader_comments(bvid)
            for comment in uploader_comments:
                if comment['rpid'] not in seen_rpids:
                    all_comments.append(comment)
                    seen_rpids.add(comment['rpid'])

            # 按时间排序（最新的在前）
            all_comments.sort(key=lambda x: x.get('ctime', 0), reverse=True)

            return all_comments

        except Exception as e:
            print(f"获取UP主相关评论失败: {e}")
            return []

    def _extract_comment_info(self, comment_data: Dict, source: str) -> Optional[Dict]:
        """提取评论信息的通用方法"""
        if not comment_data:
            return None

        member = comment_data.get('member', {})
        content = comment_data.get('content', {})

        return {
            'rpid': comment_data.get('rpid'),
            'author': member.get('uname', '匿名用户'),
            'author_mid': member.get('mid'),
            'content': content.get('message', ''),
            'likes': comment_data.get('like', 0),
            'ctime': comment_data.get('ctime', 0),
            'formatted_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(comment_data.get('ctime', 0))) if comment_data.get('ctime') else '',
            'is_owner': comment_data.get('attr', 0) == 2,
            'source': source,
            'author_info': {
                'mid': member.get('mid'),
                'avatar': member.get('avatar'),
                'level': member.get('level_info', {}).get('current_level', 0),
                'vip_status': member.get('vip', {}).get('status', 0)
            }
        }

    @staticmethod
    def parse_cookie_string(cookie_str: str) -> Dict[str, str]:
        """
        解析 cookie 字符串为字典

        Args:
            cookie_str: cookie 字符串，格式如 "key1=value1; key2=value2"

        Returns:
            cookie 字典
        """
        cookies = {}
        for item in cookie_str.split('; '):
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key] = value
        return cookies
