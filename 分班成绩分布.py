# %%
import os
import json
import re
from copy import deepcopy

import pandas as pd
import numpy as np
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, Alignment, Side, Border, PatternFill
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule


from IPython.display import display

# %% [markdown]
# ### 绘制半提琴图过程

# %%
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cbook
import seaborn as sns
from collections import OrderedDict


plt.rcParams['font.sans-serif'] = ['SimHei'] # 使用黑体
# 设置正常显示负号
plt.rcParams['axes.unicode_minus'] = False
sns_colors = sns.color_palette()

# %%
def Set_Labels(ax, title, y_len, xlabel, ylabel, tag='', normal_size=16, title_size=24):
    x1, x2 = ax.get_xlim()
    x1, x2 = int(x1), int(x2+1)
    # 设置轴标签
    ax.set_yticks(range(y_len))
    ax.set_xticks(range(x1//10*10, (x2//10)*10+1,10))
    ax.set_yticklabels(ax.get_yticklabels(), size=16)
    ax.set_xticklabels(ax.get_xticklabels(), size=16)
    ax.set_ylabel(ylabel, size=normal_size+2)
    ax.set_xlabel(xlabel, size=normal_size+2)
    ax.set_title(title, 
                 size=title_size, 
                 fontname='FZXiaoBiaoSong-B05')
    # display(ax.get_xlim())
    ax.set_ylim(y_len-0.25, -0.5)

def Draw_Lines(ax, data_des,class_list, y_start=0):
    
    def draw_line(ax, data_des_text, y_ticks):
        ax.plot(data_des_text['50%'].to_list(), y_ticks, '-o', ms=12, c='green', label='中位数')
        ax.plot(data_des_text['mean'].to_list(), y_ticks, '-o', ms=8, c='gray', label='平均数')
        ax.plot(data_des_text['75%'].to_list(), y_ticks, '-s', ms=10, c='blue', label='上四分位数')
        ax.plot(data_des_text['25%'].to_list(), y_ticks, '-s', ms=10, c='red', label='下四分位数')
        # ax.legend()
        
    if isinstance(class_list[0], list): 
        for cls_s in class_list:
            data_des_text = data_des.loc[cls_s,:]
            y_end = y_start+len(cls_s)
            y_ticks = range(y_start, y_end)
            draw_line(ax, data_des_text, y_ticks)
            y_start = y_end
    else:
        data_des_text = data_des.loc[class_list,:]
        y_ticks = range(y_start, y_start+len(class_list))
        draw_line(ax, data_des_text, y_ticks)

def Put_Stats_Info(ax, data_des, class_list, colors='black'):
    # 获取坐标轴范围
    x1, x2 = s_min, s_max
    x1, x2 = int(x1), int(x2+1)
    text_move = 0.58
    i = 0
    for k, cls_s in enumerate(class_list):
        color_text = colors[k]
        for cls in cls_s:
            if not cls in data_des.index:
                continue
            f = 1
            mean = data_des.loc[cls, 'mean']
            std = data_des.loc[cls, 'std']
            ax.text(int(x1+1), i, 
                    f'ave:{mean:.2f}\nstd:{std:>5.2f}', va='center', 
                    size=14, 
                    color=color_text
                   )
            medium = data_des.loc[cls, '50%']
            ax.text(medium, 
                    i+text_move*f, 
                    f'M:{medium:.1f}', ha='center', 
                    size=14, 
                    color=color_text               
                   )
            q1 = data_des.loc[cls, '25%']
            ax.text(q1, i+text_move*f, 
                    f'Q1:{q1:.1f}', ha='right', 
                    size=14, 
                    color=color_text
                   )
            q2 = data_des.loc[cls, '75%']
            ax.text(q2, i+text_move*f, 
                    f'Q2:{q2:.1f}', ha='left', 
                    size=14, 
                    color=color_text
                   )
            i += 1

def draw_by_category(group, tag, data_des_all, save=False, w=12, h=18, score_min=40, score_max=90):
    # 图片标题，文件标题
    title = f'{exam_title}_班级统计{tag}'
    # 画布大小h
    fig, ax = plt.subplots(figsize=(w,h))
    # 分组清单
    cls_list = list(group.values())
    target_lst = []
    for i in cls_list:
        target_lst.extend(i)
    data_des = data_des_all.loc[target_lst, :]
    
    for i, tc in enumerate(group):
        cls_name = cls_list[i]
        ax = sns.violinplot(data=data1[data1['班级'].apply(lambda x:x in cls_name)], y='班级', x='总分', 
                            order=target_lst, 
                            split=True, 
                            orient='h', 
                            fill=False, inner='quart', 
                            label=tc, 
                            # legend='full', 
                            color=sns_colors[i]
                      )

    
    Put_Stats_Info(ax, data_des, cls_list, sns_colors)
    
    Set_Labels(ax, title, len(data_des), stats_index, cate_index, tag)
    
    Draw_Lines(ax, data_des, cls_list)
    
    ax.set_xlim((score_min, score_max))
    
    handles, labels = plt.gca().get_legend_handles_labels()
    by_labels = OrderedDict(zip(labels, handles))
    ax.legend(by_labels.values(), by_labels.keys(), loc='upper right')
    
    # ax.legend()
    
    file_name = f'{exam_tar['日期'].strftime('%Y-%m-%d')}_{title}.png'
    file_folder = os.path.join(workspace, '历次考试成绩分布', tag[2:-1])
    if not os.path.exists(file_folder):
        os.makedirs(file_folder)
    file_path = os.path.join(file_folder, file_name)
    if save:
        plt.savefig(file_path, bbox_inches='tight')

# %% [markdown]
# ### 计算数据

# %%
import ExamInfo

cfg = ExamInfo.get_cfg()
exam_term = cfg['term']
workspace = f'../{exam_term}'
# exam_info, exam_tar = ExamInfo.get_exam(cfg['exam_records'], exam_num=cfg['exam_num'])
exam_info, exam_tar = ExamInfo.get_exam(cfg['exam_records'], exam_num=-1)
s_min = 25
s_max = 95
exam_title = exam_tar['名称']
print(exam_title)

# %%
data_file = f'教学班_{exam_title}_带小题分.xlsx'
data_file_path = os.path.join(workspace, exam_title, data_file)
data_lst = []
stats_index = '总分'
cate_index = '班级'
with pd.ExcelFile(data_file_path) as reader:
    for sheet in reader.sheet_names:
        datai = pd.read_excel(data_file_path, sheet_name=sheet)
        datai = datai[datai['姓名'].notna()][[stats_index]]
        datai.loc[:, cate_index] = sheet
        data_lst.append(datai)
data = pd.concat(data_lst, ignore_index=True)
data1 = data.copy()

# %% [markdown]
# ### 绘图

# %%
data_des_all = data1[[cate_index, stats_index]].groupby(cate_index).describe().T.reset_index(level=0, drop=True).T

width = 13
height= 18
cetagory_lists = [cfg['class_type'], cfg['class_tch']]
cetagory_tag = ['（按班级分组）', '（按教师分组）']
r = data_des_all['50%'].rank(ascending=False)
for i in range(len(cetagory_lists)):
    lst = cetagory_lists[i]
    # lst = [i for i in lst if i in data_des_all.index]
    # 组内按照其他参数排序
    for k in lst.keys():
        cls_lst = [i for i in lst[k] if i in data_des_all.index]
        cls_lst.sort(key=lambda x:r[x])
        lst[k] = cls_lst
    # 
    
    tag = cetagory_tag[i]
    draw_by_category(lst, tag, data_des_all, True, w=width, h=height, score_min=s_min, score_max=s_max)

# %%


# %%



