"""Inspect decoder IR — check for past KV inputs, etc."""
import openvino as ov
m = ov.Core().read_model('models/ov-int8/openvino_decoder_model.xml')
ins = [(i.get_any_name(), str(i.partial_shape), i.get_element_type().get_type_name()) for i in m.inputs]
print('decoder inputs:')
for n, sh, ty in ins:
    print(f'  IN  {n}: {sh} {ty}')
print('outputs (count):', len(m.outputs))

# Read the XML directly
with open('models/ov-int8/openvino_decoder_model.xml', 'r', encoding='utf-8') as f:
    content = f.read()
import re
xml_ins = sorted(set(re.findall(r'<\s*input[^>]*name="([^"]+)"', content)))
xml_outs = sorted(set(re.findall(r'<\s*output[^>]*name="([^"]+)"', content)))
print('XML inputs:', xml_ins)
print('XML outputs (', len(xml_outs), 'total):', xml_outs[:5], '...', xml_outs[-3:])
print('XML past count:', content.count('past'))
print('XML attention_mask count:', content.count('attention_mask'))
print('XML position_ids count:', content.count('position_ids'))