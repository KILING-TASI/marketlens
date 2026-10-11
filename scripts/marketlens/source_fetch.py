# SPDX-License-Identifier: MIT
"""Explicit public HTTPS download; redirects revalidated, IP pinned for request."""
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin

def fetch(url):
    chain=[]
    for _ in range(4):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443): raise ValueError('只支持无账号信息的公开HTTPS地址和443端口')
        addresses=socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses): raise ValueError('不访问内网、回环或非公开地址')
        family,kind,protocol,_,address=addresses[0]
        connection=http.client.HTTPSConnection(parsed.hostname,timeout=20)
        raw=socket.socket(family,kind,protocol);raw.settimeout(20)
        try:
            raw.connect(address)
            connection.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=parsed.hostname)
            connection.request('GET',(parsed.path or '/')+('?' + parsed.query if parsed.query else ''),headers={'User-Agent':'MarketLens/0.4.0 source-check','Accept-Encoding':'identity'})
            response=connection.getresponse()
            chain.append(dict(url=url,status=response.status))
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location: raise ValueError('重定向缺少目标')
                url=urljoin(url,location);continue
            if response.status!=200: raise ValueError('来源返回HTTP '+str(response.status)+'；未取得原文')
            if response.getheader('Content-Encoding','identity')!='identity': raise ValueError('来源返回压缩传输；请用浏览器保存原文件')
            body=response.read(16*1024*1024+1)
            if len(body)>16*1024*1024: raise ValueError('原文件超过16MiB')
            return body,dict(finalUrl=url,redirectChain=chain,contentType=response.getheader('Content-Type'),status=response.status,publisherAuthenticated=False,scope='TLS与实际下载不认证消息真实性或网页版本')
        except http.client.HTTPException as error:
            raise ValueError('HTTPS响应无法读取：'+str(error)) from error
        finally:
            connection.close();raw.close()
    raise ValueError('重定向次数超过限制')
