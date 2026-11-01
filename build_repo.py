from pathlib import Path
import subprocess, hashlib, gzip, bz2
from datetime import datetime, timezone

root = Path(__file__).resolve().parent

# 源的对外根地址。图标写成绝对 URL，是因为相对路径各家客户端（Sileo/Zebra/Cydia）
# 支持程度不一致，绝对 URL 最保险。将来换域名只改这一行，重跑一次索引即可，
# deb 包和 Packages 结构都不用动。
BASE_URL = 'https://vipios.github.io/'

# 图标本地化（2026-11-01）
# ---------------------------------------------------------------
# 原来每个包的 Icon 指回作者自己的站点：muzikeji / s1.imagehub.cc /
# chinesebuilding.club / jimkanuo / axs66 一共 7 个域名。Sileo 刷新索引时会把
# 所有图标一起拉，等于每次刷新多付 7 次 DNS + TLS 握手；更糟的是
# chinesebuilding.club 开了防盗链直接 403、jimkanuo 那张 404，客户端还得白等。
# 实测一次完整刷新 2.18 秒，其中本项目自己的 Release + Packages 只占 0.40 秒，
# 剩下全是图标在拖。
#
# 现在统一改成本仓库 icons/ 目录下的压缩图（256px，单张 1–11KB，合计 28KB）。
# 找不到本地图标的包：原来是 file:// 的（读设备本地文件，不发网络请求）保留，
# 原来是 http(s) 的一律去掉 Icon 字段，交给客户端显示默认占位图——
# 宁可少一个图标，也不要每次刷新都去等一个 403/404。
ICON_DIR = root / 'icons'


def local_icon(pkg):
    """本仓库里该包图标的相对路径，没有则返回 None。"""
    if not pkg:
        return None
    for ext in ('.png', '.jpg', '.jpeg'):
        f = ICON_DIR / (pkg + ext)
        if f.is_file():
            return 'icons/' + pkg + ext
    return None


entries = []
architectures = set()
for p in sorted((root / 'debs').rglob('*.deb')):
    control = subprocess.check_output(['dpkg-deb', '-f', str(p)], text=True).strip()
    fields = dict(line.split(':', 1) for line in control.splitlines() if line and not line.startswith((' ', '\t')) and ':' in line)
    for key in ('Package', 'Version', 'Architecture'):
        if not fields.get(key, '').strip():
            raise ValueError(f'{p}: missing {key}')
    architectures.add(fields['Architecture'].strip())
    data = p.read_bytes()

    pkg = fields['Package'].strip()
    old_icon = ''
    kept = []
    for line in control.splitlines():
        if line.startswith(('Filename:', 'Size:', 'MD5sum:', 'SHA1:', 'SHA256:')):
            continue
        if line.startswith('Icon:'):
            # 只在这里记下来，稍后按本地有没有压缩图决定放什么
            old_icon = line.split(':', 1)[1].strip()
            continue
        kept.append(line)

    icon = local_icon(pkg)
    if icon:
        kept.append('Icon: ' + BASE_URL + icon)
    elif old_icon.startswith('file://'):
        kept.append('Icon: ' + old_icon)

    control = '\n'.join(kept)
    entries.append(control + '\nFilename: ' + p.relative_to(root).as_posix() + '\nSize: ' + str(len(data)) + '\nMD5sum: ' + hashlib.md5(data).hexdigest() + '\nSHA1: ' + hashlib.sha1(data).hexdigest() + '\nSHA256: ' + hashlib.sha256(data).hexdigest() + '\n\n')

data = ''.join(entries).encode()
(root / 'Packages').write_bytes(data)
(root / 'Packages.gz').write_bytes(gzip.compress(data, mtime=0))
(root / 'Packages.bz2').write_bytes(bz2.compress(data))
release = 'Origin: 不知道起什么名\nLabel: 不知道起什么名\nSuite: stable\nCodename: stable\nVersion: 1.0\nArchitectures: ' + ' '.join(sorted(architectures or {'iphoneos-arm', 'iphoneos-arm64', 'iphoneos-arm64e'})) + '\nComponents: main\nDescription: vipios 的 Sileo 软件源\nDate: ' + datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000') + '\n'
for heading, alg in [('MD5Sum', 'md5'), ('SHA1', 'sha1'), ('SHA256', 'sha256')]:
    release += heading + ':\n'
    for name in ('Packages', 'Packages.gz', 'Packages.bz2'):
        b = (root / name).read_bytes()
        release += f' {hashlib.new(alg, b).hexdigest()} {len(b)} {name}\n'
(root / 'Release').write_text(release)
print('Indexed', len(entries), 'packages')
