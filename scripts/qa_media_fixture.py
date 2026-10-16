"""Generate a tiny original video for API and browser acceptance tests."""
import io
import sys
from pathlib import Path

import av
from PIL import Image, ImageDraw


def video_bytes(container_format='mp4', codec='libx264'):
    output = io.BytesIO()
    with av.open(output, mode='w', format=container_format) as container:
        stream = container.add_stream(codec, rate=12)
        stream.width, stream.height = 320, 180
        stream.pix_fmt = 'yuv420p'
        for index in range(24):
            picture = Image.new('RGB', (320, 180), '#326b65')
            ImageDraw.Draw(picture).ellipse((index * 8, 50, index * 8 + 60, 110), fill='#e9cf91')
            for packet in stream.encode(av.VideoFrame.from_image(picture)):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return output.getvalue()


if __name__ == '__main__':
    Path(sys.argv[1]).write_bytes(video_bytes())
