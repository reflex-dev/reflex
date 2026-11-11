p='blog/models.py'; s=open(p).read(); s=s.replace("rx.ModelRegistry.register(Base)\n","",1); open(p,'w').write(s)
