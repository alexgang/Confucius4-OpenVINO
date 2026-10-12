import os, sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf
from transformers import WhisperFeatureExtractor

fe = WhisperFeatureExtractor.from_pretrained('models/hf')
audio, sr = sf.read('C:/Users/Trekker-PTL/confucius4-r2t2/test.wav')
audio = audio.astype(np.float32)
print('audio', len(audio), 'samples', float(len(audio)/sr), 's', flush=True)

# Default call (what backends.py does)
out = fe(list(audio), sampling_rate=16000, return_tensors='np')
print('default', out['input_features'].shape, 'mask sum', out['attention_mask'].sum(), flush=True)

out2 = fe(list(audio), sampling_rate=16000, return_tensors='np', padding='do_not_pad')
print('do_not_pad', out2['input_features'].shape, flush=True)

out3 = fe(list(audio), sampling_rate=16000, return_tensors='np', return_attention_mask=False)
print('no_mask', out3['input_features'].shape, flush=True)

out4 = fe(list(audio), sampling_rate=16000, return_tensors='np',
          padding=True, truncation=False)
print('qwen_asr_style padding=True truncation=False', out4['input_features'].shape,
      'mask', out4['attention_mask'].shape, 'sum', out4['attention_mask'].sum(), flush=True)
