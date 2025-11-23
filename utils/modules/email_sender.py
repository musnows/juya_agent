"""
邮件发送模块
支持 HTML 格式的邮件发送
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from pathlib import Path
from dotenv import load_dotenv

from ..logger import get_logger


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _str_to_bool(value: str, default: bool = False) -> bool:
    """将环境变量字符串安全地转换为布尔值"""
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


class EmailSender:
    """邮件发送器"""

    def __init__(self, from_email: str = None, smtp_password: str = None,
                 smtp_server: str = None, smtp_port: int = None, use_ssl: bool = None, timeout: int = None):
        """
        初始化邮件发送器

        Args:
            from_email: 发件人邮箱
            smtp_password: SMTP 密码/授权码
            smtp_server: SMTP 服务器地址
            smtp_port: SMTP 端口
        """
        # 使用统一的日志器
        self.logger = get_logger()
        # 如果未提供参数，从项目根目录的 .env 读取，避免依赖当前工作目录
        load_dotenv(PROJECT_ROOT / ".env")

        env_use_ssl = _str_to_bool(os.getenv('SMTP_USE_SSL'), default=False)
        default_port = '465' if env_use_ssl else '587'

        self.from_email = from_email or os.getenv('EMAIL_FROM')
        self.smtp_password = smtp_password or os.getenv('SMTP_PASSWORD')
        self.smtp_server = smtp_server or os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        port_value = smtp_port or os.getenv('SMTP_PORT', default_port)
        self.smtp_port = int(str(port_value))
        self.use_ssl = use_ssl if use_ssl is not None else env_use_ssl
        timeout_value = timeout or os.getenv('SMTP_TIMEOUT', '30')
        self.timeout = int(str(timeout_value))

        if not all([self.from_email, self.smtp_password, self.smtp_server]):
            raise ValueError("邮件配置不完整，请检查环境变量或传入参数")

    def send_html_email(self, to_email: str, subject: str, html_content: str,
                        text_content: str = None, max_retries: int = 5) -> bool:
        """
        发送 HTML 格式的邮件（自动重试）

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML 格式的邮件正文
            text_content: 纯文本格式的邮件正文（备用）
            max_retries: 最大重试次数（默认5次）

        Returns:
            发送是否成功
        """
        import time

        for attempt in range(1, max_retries + 1):
            try:
                # 创建邮件对象
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = self.from_email
                msg['To'] = to_email

                # 添加纯文本和 HTML 内容
                if text_content:
                    part1 = MIMEText(text_content, 'plain', 'utf-8')
                    msg.attach(part1)

                part2 = MIMEText(html_content, 'html', 'utf-8')
                msg.attach(part2)

                # 连接 SMTP 服务器并发送
                smtp_cls = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP
                with smtp_cls(self.smtp_server, self.smtp_port, timeout=self.timeout) as server:
                    if not self.use_ssl:
                        server.ehlo()
                        if server.has_extn('starttls'):
                            server.starttls()
                            server.ehlo()
                        else:
                            self.logger.warning("Server does not support STARTTLS, continuing with unencrypted connection")
                    server.login(self.from_email, self.smtp_password)
                    server.send_message(msg)

                self.logger.info(f"Email sent successfully (attempt {attempt})")
                return True

            except smtplib.SMTPException as e:
                self.logger.error(f"SMTP error (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    wait_time = attempt * 2  # 递增等待时间：2秒、4秒、6秒...
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error("Max retry attempts reached, email sending failed")
                    return False

            except (ConnectionError, TimeoutError, OSError) as e:
                self.logger.error(f"Connection error (attempt {attempt}/{max_retries}): {type(e).__name__}: {e}")
                if attempt < max_retries:
                    wait_time = attempt * 2
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error("Max retry attempts reached, email sending failed")
                    return False

            except Exception as e:
                self.logger.error(f"Email sending failed (attempt {attempt}/{max_retries}): {type(e).__name__}: {e}")
                if attempt < max_retries:
                    wait_time = attempt * 2
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error("Max retry attempts reached, email sending failed")
                    return False

        return False

    def send_video_report(self, to_email: str, video_title: str, bvid: str,
                          html_content: str, markdown_path: str = None) -> bool:
        """
        发送视频报告邮件

        Args:
            to_email: 收件人邮箱
            video_title: 视频标题
            bvid: 视频 BV 号
            html_content: HTML 格式的邮件内容
            markdown_path: Markdown 文件路径（用于提示）

        Returns:
            发送是否成功
        """
        subject = f"Juya New Video: {video_title[:50]}"

        # 在 HTML 末尾添加文件路径提示
        if markdown_path:
            html_content += f"<p><strong>本地文件：</strong>{markdown_path}</p>"

        return self.send_html_email(to_email, subject, html_content)
