import sys
sys.path.insert(0, 'I:/TuminhAgi')
from soul_vault.SOUL_IMMUTABLE import DNA, NAME

print('Name:', NAME)
for d in DNA:
    print(' ', d['virtue'], '-', d['en'])
print('All good!')
