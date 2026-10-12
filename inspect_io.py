"""inspect_io.py — 打印 with-past decoder 的输入输出清单"""
import re
xml = open('models/ov-fp16-past/openvino_decoder_model.xml').read()

pat_param = re.compile(r'<layer id="(\d+)" name="([^"]+)" type="Parameter"[^>]*>\s*<data\s+([^/]+?)/>', re.S)
print("=== Parameters (inputs) ===")
for m in pat_param.finditer(xml):
    print(f"  id={m.group(1)}  name={m.group(2)}  data=<{m.group(3).strip()}>")
print()

# Results use output_names attribute
pat_result = re.compile(r'<layer id="(\d+)" name="([^"]+)" type="Result"[^>]*>', re.S)
print("=== Results (outputs) ===")
for m in pat_result.finditer(xml):
    line = m.group(0)
    om = re.search(r'output_names="([^"]+)"', line)
    print(f"  id={m.group(1)}  name={m.group(2)}  output_names={om.group(1) if om else '?'}")
print()

# Past KV init via ReadValue -> Assign pairs
pat_rv = re.compile(r'<layer id="(\d+)" name="(ReadValue_[^"]+)"[^>]*>\s*<data\s+([^/]+?)/>', re.S)
rvs = list(pat_rv.finditer(xml))
print(f"=== ReadValue layers (init past KV): {len(rvs)} samples ===")
for m in rvs[:3]:
    print(f"  id={m.group(1)}  data=<{m.group(3).strip()}>")

# Count unique output_names (past_key_values.N, present.N, etc.)
pat_o = re.compile(r'output_names="([^"]+)"', re.S)
ons = pat_o.findall(xml)
unique = sorted(set(ons))
print(f"\n=== unique output_names ({len(unique)}) ===")
for n in unique[:20]:
    print(f"  {n}")
