import os
p=os.path.join(r'F:\Conda\envs\musical_v\Lib\site-packages','riffusion')
for root,dirs,files in os.walk(p):
    if os.path.basename(root)=='seed_images':
        print('found',root)
        print(files[:50])
        break
else:
    print('no seed_images found')
