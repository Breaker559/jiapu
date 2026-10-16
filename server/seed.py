from .db import Record, uid

FAMILY = {'name':'陈氏家族','subtitle':'把相聚的时光，留给未来的我们。','surname':'陈','hometown':'浙江 · 杭州','hall':'颍川堂','motto':'认真生活，彼此牵挂。','description':'从祖辈的故乡，到我们各自的远方，每一段人生都值得被记住。这里记录家人的故事，也连接下一次相聚。','theme':'teal','timezone':'Asia/Shanghai','demo':True}

def example():
    people = [
        ('p1','陈启明','male',1942,5,12,'第一代','家族长辈','一生热爱书法与园艺，常与孩子们讲起老家的故事。'),
        ('p2','林淑华','female',1945,8,15,'第一代','家族长辈','喜欢烹饪和摄影，家中的老照片大多由她收藏。'),
        ('p3','陈建国','male',1968,3,21,'第二代','长房','工程师，喜欢徒步，是家族聚会的组织者。'),
        ('p4','周雅琴','female',1970,11,6,'第二代','长房','中学教师，热心记录家族的口述故事。'),
        ('p5','陈建宁','male',1972,7,18,'第二代','二房','在苏州生活，热爱音乐和旅行。'),
        ('p6','陈晓云','female',1976,2,8,'第二代','三房','喜欢种花与阅读，经常回故乡探望长辈。'),
        ('p7','陈予安','male',1996,10,22,'第三代','长房','产品设计师，正在整理全家的照片和回忆。'),
        ('p8','陈知夏','female',2000,6,5,'第三代','长房','大学毕业后成为建筑师，喜欢记录城市生活。'),
        ('p9','陈一诺','female',2004,12,2,'第三代','二房','在读大学生，喜欢摄影和自然。'),
        ('p10','王思远','male',1974,4,16,'第二代','三房','从事教育工作，喜欢骑行。'),
        ('p11','王星禾','female',2006,9,9,'第三代','三房','热爱绘画与文学。'),
    ]
    records=[]
    for id,name,gender,y,m,d,generation,branch,bio in people:
        records.append({'id':id,'kind':'person','data':{'name':name,'gender':gender,'generation':generation,'branch':branch,'birth':{'calendar':'lunar' if id=='p2' else 'solar','year':y,'month':m,'day':d,'leap':False},'death':{},'living':True,'birthplace':'浙江杭州','bio':bio,'source':'产品演示资料（所有人物均为虚构）','privacy':'family','anniversary_calendar':'original','leap_policy':'regular','missing_policy':'last','aliases':'','avatar':''},'version':1})
    pairs=[('p1','p2','married'),('p3','p4','former_spouse'),('p6','p10','coparent'),('p1','p3','parent'),('p2','p3','parent'),('p1','p5','parent'),('p2','p5','parent'),('p1','p6','parent'),('p2','p6','parent'),('p3','p7','parent'),('p4','p7','parent'),('p3','p8','parent'),('p4','p8','parent'),('p5','p9','adoptive'),('p6','p11','parent'),('p10','p11','parent')]
    for i,(a,b,kind) in enumerate(pairs):
        note='仅示例共同育儿，不表示婚姻或伴侣关系。' if kind=='coparent' else '婚姻已结束，分别保留与子女的关系。' if kind=='former_spouse' else ''
        records.append({'id':f'r{i}','kind':'relation','data':{'from_id':a,'to_id':b,'type':kind,'certainty':'confirmed','note':note,'source':'演示资料（虚构）'},'version':1})
    records += [
      {'id':'s1','kind':'story','data':{'format':'markdown','title':'把散落的记忆，慢慢收集起来','body':'一张照片、一段口述、一个熟悉的名字，都是家族故事的起点。\n\n试着从一位你熟悉的长辈开始，补充他的经历，邀请家人一起留下记忆。此处内容为产品演示，可在创建自己的家族后修改。','category':'家族故事','date':{'calendar':'solar','year':2026,'month':10,'day':1},'person_ids':['p1','p2'],'privacy':'family','source':'产品演示'},'version':1},
      {'id':'s2','kind':'story','data':{'format':'markdown','title':'整理老照片的三个线索','body':'先记下拍摄时间和地点，再辨认照片中的人物。\n不确定的细节先写在备注中，等家人一起确认。原图会与人物资料一起保存。','category':'修谱笔记','date':{'calendar':'solar','year':2026,'month':10,'day':8},'person_ids':[],'privacy':'family','source':'产品演示'},'version':1}
    ]
    return records

def seed_family(db, family_id):
    records=example(); mapping={r['id']:uid() for r in records}
    for r in records:
        data=r['data']
        for key in ('from_id','to_id'):
            if key in data: data[key]=mapping[data[key]]
        if 'person_ids' in data:data['person_ids']=[mapping[x] for x in data['person_ids']]
        db.add(Record(id=mapping[r['id']],family_id=family_id,kind=r['kind'],data=data))
