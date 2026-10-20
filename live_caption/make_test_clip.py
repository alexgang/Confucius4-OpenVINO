"""Cut a 60 s English test clip (12:00-13:00 of the SPE recording) for headless self-tests."""
import os
import soundfile as sf

src = r'C:\Users\Trekker-PTL\confucius4-openvino\test_audio\<redacted>.wav'
a, sr = sf.read(src, dtype='float32')
if a.ndim > 1:
    a = a[:, 0]
dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_en_60s.wav')
sf.write(dst, a[720 * sr:780 * sr], sr)
print(dst, sr, round(len(a) / sr, 1))
