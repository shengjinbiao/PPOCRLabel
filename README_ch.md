[English](README.md) | ��������

# PPOCRLabelv3

[![PyPI - Version](https://img.shields.io/pypi/v/PPOCRLabel)](https://pypi.org/project/PPOCRLabel/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/PPOCRLabel)](https://github.com/PFCCLab/PPOCRLabel)
[![Downloads](https://static.pepy.tech/badge/PPOCRLabel)](https://github.com/PFCCLab/PPOCRLabel)

PPOCRLabelv3��һ��������OCR����İ��Զ���ͼ�α�ע���ߣ�����PP-OCRģ�Ͷ������Զ���ע������ʶ��ʹ��Python3��PyQT5��д��֧�־��ο��ע������ע���������ı���ע���ؼ���Ϣ��עģʽ��������ʽ��ֱ������PaddleOCR����ʶ��ģ�͵�ѵ����

|                      �����ע                       |                    ����ע                    |
| :-------------------------------------------------: | :--------------------------------------------: |
|  <img src="./data/gif/steps_en.gif" width="80%"/>   | <img src="./data/gif/table.gif" width="100%"/> |
|                 **�������ı���ע**                  |                **�ؼ���Ϣ��ע**                |
| <img src="./data/gif/multi-point.gif" width="80%"/> |  <img src="./data/gif/kie.gif" width="100%"/>  |

#### ���ڸ���
- 2025.11:
  - ����`PaddleOCR ���ģ��ѵ��`��ڣ����ڲ˵���һ�����ѵ����ʵʱ�鿴��־/ֹͣ���񣬲�֧���Զ�����ѵ�����á�
  - ֧�ִӵ�ǰ�򿪲�����ɱ�ע��Ŀ¼�Զ����ѵ��/��֤���ݼ���ʡȥ�ֶ����� `train.txt`/`val.txt` �Ĳ��衣
  - ����`�Զ�����/ʶ��ģ��`ѡ���������г�`C:\Users\<name>\.paddlex\official_models`�Լ��Զ���Ŀ¼�µ�ģ�ͣ�֧��һ���л���ָ�Ĭ��ģ�͡�
  - ���Զ���ע��ǰҳ�������Ż�����ť����ͬһҳ�淴��ִ�С�������ǿ����ҳ���ѱ�עҳ��Ҳ����ֱ�������Զ�ʶ��
- 2025.06:
  - ����`�������������λ��`���ܣ�ʹ�÷�������·�`2.1 ��������`��`11. ���书��˵��`��
- 2024.11:
  - ����`label_font_path`�����������ı��ǩ����
  - ����`selected_shape_color`�����������ı�ѡ�б�ǩ���������ɫ
- 2024.09:
  - ����`�Զ�����ʶ��`��`�Զ�����δ�ύ���`���ܣ�ʹ�÷�������·�`2.1 ��������`��`11. ���书��˵��`��
  - ����`--img_list_natural_sort`������Ĭ�����ͼƬ�б�ʹ����Ȼ�������øò����󣬽�ʹ���ַ����򣬷�������ַ�˳��λͼƬ��
  - ����4���Զ���ģ�͵Ĳ�����
    - `det_model_dir` �����ģ��Ŀ¼·��
    - `rec_model_dir` ��ʶ��ģ��Ŀ¼·��
    - `rec_char_dict_path` ��ʶ��ģ���ֵ��ļ�·��
    - `cls_model_dir` ������ģ��Ŀ¼·��
  - ����`--bbox_auto_zoom_center`��������ͼƬֻ��һ����ǿ��ʱ�򣬿��Կ�������Զ�����ǿ���зŴ�
  - ����5�����Ʊ�ǿ�4������Ŀ�ݼ�`z`��`x`��`c`��`v`��`b`��ʹ�÷�������·�`2.1 ��������`��`11. ���书��˵��`��
- 2022.05��**��������ע**��ʹ�÷������·�`2.2 ����ע`��by [whjdark](https://github.com/peterh0323); [Evezerest](https://github.com/Evezerest)��
- 2022.02��**�����ؼ���Ϣ��ע**���Ż���ע���飨by [PeterH0323](https://github.com/peterh0323) ��
  - ������ʹ�� `--kie` ���� KIE ���ܣ����ڴ򡾼��+ʶ��+�ؼ�����ȡ���ı�ǩ
  - �����û����飺�����ļ�������Ŀ��ʾ���Ż��������޸�gpuʹ�õ����⡣
  - �������ܣ�ʹ�� `C` �� `X` �Ա�ǿ������ת��
- 2021.11.17��
  - ����֧��ͨ��whl����װ�����PPOCRLabel��by [d2623587501](https://github.com/d2623587501)��
  - ��ע���ݼ��з֣��Ա�ע���ݽ���ѵ������֤����Լ����֣��ο��·�3.5�ڣ�by [MrCuiHao](https://github.com/MrCuiHao)��
- 2021.8.11��
  - �������ܣ������������ļ��С��Ҽ�ͼ����ת90�ȣ�ע�⣺��תǰ��ͼƬ�ϲ��ܴ��ڱ�ǿ�by [Wei-JL](https://github.com/Wei-JL)��
  - ������ݼ�˵��������-��ݼ������޸��������µķ����ݼ��ƶ����ܣ�by [d2623587501](https://github.com/d2623587501)��
- 2021.2.5�������������볷�����ܣ�by [Evezerest](https://github.com/Evezerest)��
  - **���������**����סCtrl��ѡ���ǿ��������ƶ������ơ�ɾ��������ʶ��
  - **��������**���ڻ����ĵ��ע������л�Կ���б༭�����󣬰���Ctrl+Z�ɳ�����һ��������
  - �޸�ͼ����ת�ͳߴ����⡢�Ż��༭��ǿ���̣�by [ninetailskim](https://github.com/ninetailskim)�� [edencfc](https://github.com/edencfc)��
- 2021.1.11���Ż���ע���飨by [edencfc](https://github.com/edencfc)����
  - �û����ڡ���ͼ - ������������ѡ���ڻ���������������Ƿ񵯳���
  - ʶ���������ͬ��������
  - ʶ��������Ϊ�����޸ġ�������޷��޸ģ����л�Ϊϵͳ�Դ����뷨�����ٴ��л�ԭ���뷨��
- 2020.12.18�� ֧�ֶԵ�����ǿ��������ʶ��by [ninetailskim](https://github.com/ninetailskim)�������ƿ�ݼ���

����������ƹ����в�һ�����뷨����ӭͨ��[����������](https://github.com/PaddlePaddle/PaddleOCR/issues/4982)������ظ��ģ���û��ֶһ�������



## 1. ��װ������

### 1.1 ��װPaddlePaddle

```bash
pip3 install --upgrade pip

# ������Ļ�����CPU���������������װ
python3 -m pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

����İ汾���������[��װ�ĵ�](https://www.paddlepaddle.org.cn/install/quick)�е�˵�����в�����

### 1.2 ��װ������PPOCRLabel

PPOCRLabel��ͨ��whl����Python�ű����ַ�ʽ�����whl����ʽ������ӷ��㣬python�ű�������ڶ��ο���

#### 1.2.1 ͨ��whl����װ������

##### Windows

```bash
pip install PPOCRLabel  # ��װ

# ѡ���ǩģʽ�����
PPOCRLabel --lang ch  # �������ͨģʽ�������ڴ򡾼��+ʶ�𡿳����ı�ǩ
PPOCRLabel --lang ch --kie True  # ��� ��KIE ģʽ�������ڴ򡾼��+ʶ��+�ؼ�����ȡ�������ı�ǩ
```
> ע�⣺ͨ��whl����װPPOCRLabel���Զ����� `paddleocr` whl��������shapely�������ܻ���� `[winRrror 126] �Ҳ���ָ��ģ������⡣` �Ĵ��󣬽����[����](https://www.lfd.uci.edu/~gohlke/pythonlibs/#shapely)���ز���װ
##### Ubuntu Linux

```bash
pip3 install PPOCRLabel
pip3 install trash-cli
export QT_QPA_PALTFORM = wayland # ���Կ�����ӵ�ϵͳ���������У�����������
# ѡ���ǩģʽ�����
PPOCRLabel --lang ch  # �������ͨģʽ�������ڴ򡾼��+ʶ�𡿳����ı�ǩ
PPOCRLabel --lang ch --kie True  # ��� ��KIE ģʽ�������ڴ򡾼��+ʶ��+�ؼ�����ȡ�������ı�ǩ
```

##### MacOS
```bash
pip3 install PPOCRLabel
pip3 install opencv-contrib-python-headless==4.2.0.32 # ������ع��������"-i https://mirror.baidu.com/pypi/simple"

# ѡ���ǩģʽ�����
PPOCRLabel --lang ch  # �������ͨģʽ�������ڴ򡾼��+ʶ�𡿳����ı�ǩ
PPOCRLabel --lang ch --kie True  # ��� ��KIE ģʽ�������ڴ򡾼��+ʶ��+�ؼ�����ȡ�������ı�ǩ
```

> ���������װ�������⣬���Բο�3.6�� ������ʾ

#### 1.2.2 ͨ��Python�ű�����PPOCRLabel

�������PPOCRLabel�ļ��������ģ�����ָ���µ�����ģ�ͣ���ͨ��Python�ű����л���ӷ���Ŀ������ĵĽ���������Ȼ��Ҫͨ��whl�����������Ҫ��ж�ص�ǰ�����е�whl����Ȼ��ο��½����±���whl����

```bash
cd ./PPOCRLabel  # �л���PPOCRLabelĿ¼
python PPOCRLabel.py --lang ch
```

#### 1.2.3 ���ع���whl������װ

```bash
cd ./PPOCRLabel
pip install -e .
```

#### 1.2.4 Pyinstaller���������
```bash
cd ./PPOCRLabel
# ��װpyinstaller
pip install pyinstaller

# ����������Դ
pyrcc5 -o libs/resources.py resources.qrc

# �����ִ�г���
pyinstaller -c PPOCRLabel.py --collect-all paddleocr --collect-all pyclipper --collect-all imghdr --collect-all skimage --collect-all imgaug --collect-all scipy.io --collect-all lmdb --collect-all paddle --hidden-import=pyqt5  -p ./libs -p ./ -p ./data -p ./resources -F

# ����dist�еĿ�ִ�г�����windowsΪ��
PPOCRLabel.exe --lang ch
```

## 2. ʹ��

### 2.1 ��������

> �����ֻ��Ҫ��ע������Ϣ��λ�ã��Ƽ��������²���չ����

1. ��װ�����У�ʹ���������װ�����г���
2. ���ļ��У��ڲ˵������ ���ļ��� - "��Ŀ¼" ѡ������ͼƬ���ļ���<sup>[1]</sup>.
3. �Զ���ע����� ���Զ���ע����ʹ��PP-OCR������ģ�Ͷ�ͼƬ�ļ���ǰͼƬ״̬<sup>[2]</sup>Ϊ ��X�� ��ͼƬ�����Զ���ע��
4. �ֶ���ע����� �����α�ע�����Ƽ�ֱ����Ӣ��ģʽ�µ�������е� ��W��)���û��ɶԵ�ǰͼƬ��ģ��δ����Ĳ��ֽ����ֶ����Ʊ�ǿ򡣵������Q����ʹ���ĵ��עģʽ���������༭�� - ���ĵ��ע�������û����ε��4�����˫�������ʾ��ע��ɡ�
5. ��ǿ������ɺ��û���� ��ȷ�ϡ���������ȱ�Ԥ����һ�� ����ʶ�� ��ǩ��
6. ����ʶ�𣺽�ͼƬ�е����м�⻭����/������ɺ󣬵�� ������ʶ�𡱣�PP-OCRģ�ͻ�Ե�ǰͼƬ�е�**���м���**����ʶ��<sup>[3]</sup>��
7. ���ݸ��ģ�����ʶ�������Բ�׼ȷ��ʶ���������ֶ����ġ�
8. **ȷ�ϱ�ǣ���� ��ȷ�ϡ���ͼƬ״̬�л�Ϊ ���̡�����ת����һ�š�**
9. ɾ������� ��ɾ��ͼ�񡱣�ͼƬ���ᱻɾ��������վ��
10. ����������û�����ͨ���˵��С��ļ�-������ǽ�����ֶ�������ͬʱҲ���Ե�����ļ� - �Զ�������ǽ���������Զ��������ֶ�ȷ�Ϲ��ı�ǽ��ᱻ���������ͼƬ�ļ����µ�*Label.txt*�С��ڲ˵������ ���ļ��� - "����ʶ����"�󣬻Ὣ����ͼƬ��ʶ��ѵ�����ݱ�����*crop_img*�ļ����£�ʶ���ǩ������*rec_gt.txt*��<sup>[4]</sup>��
11. ���书��˵��
    - `�ļ�` -> `�Զ�����ʶ��` : ��ѡ�󣬶����±�ע�Ŀ����ݻ��Զ�������ǰ��ע�������ʶ���ܣ�����Ҫ��ȥ���`����ʶ��`��ť���ʺϸ���ԭ����ʹ��`�Զ���ע`ֻ���ֶ���ע�ĳ��������糵��ʶ��һ��ͼ��ֻ��һ�����ƣ����ʹ��`�Զ���ע`,��Ҫɾ���ܶ����ʶ����������ֿ򣬲���ֱ�����±�ע
    - `�ļ�` -> `�Զ�����δ�ύ���` : Ĭ���ǰ�`ȷ��`��ť��ɵ�ǰ��ı��ȷ�ϣ��е㷱������ѡ���л���һ��ͼ������ݼ�`D`����ʱ�򣬲��ٵ�����ʾ��ȷ���Ƿ񱣴�δȷ�ϵı�ǣ��Զ����浱ǰ��ǲ��л���һ��ͼ��������ٱ��
    - ѡ�б�ǿ��5�����Կ��Ʊ�ǿ��ĸ����㵥���ƶ��Ŀ�ݼ����ʺ���Ҫ��ȷ���Ʊ�ǿ��ĸ�����λ�õĳ���
      - `z` �����º󣬴�ʱʹ�ü��̵��������Ұ����������ƶ���1������
      - `x` �����º󣬴�ʱʹ�ü��̵��������Ұ����������ƶ���2������
      - `c` �����º󣬴�ʱʹ�ü��̵��������Ұ����������ƶ���3������
      - `v` �����º󣬴�ʱʹ�ü��̵��������Ұ����������ƶ���4������
      - `b` �����º󣬴�ʱʹ�ü��̵��������Ұ������ָ�Ĭ�ϵ������ƶ�������ǿ�
    - `���·�` -> `��������λ��` : �����Ὣ��ע���մ��ϵ��¡������ҵ�˳��������С����ڽ�����ṹ��ʶʱ����Ҫ�ֶ�������α�ʶ���˳��������⡣

### 2.2 ����ע��[��Ƶ��ʾ](https://www.bilibili.com/video/BV1wR4y1v7JE/?share_source=copy_web&vd_source=cf1f9d24648d49636e3d109c9f9a377d&t=1998)��

����ע��Ա��Ľṹ����ȡ����ͼƬ�еı��ת��ΪExcel��ʽ����˱�עʱ��Ҫ����ⲿ�����Excelͬʱ��ɡ���PPOCRLabel�������ɱ���е�������Ϣ��ע��������λ�ã�����Excel�ļ�����ɱ��ṹ��Ϣ��ע���Ƽ��Ĳ���Ϊ��
1. ���ʶ�𣺴򿪱��ͼƬ�󣬵��������Ͻ� `���ʶ��` ��ť���������PP-Structure�еı��ʶ��ģ�ͣ��Զ�Ϊ�����ǩ��ͬʱ����Excel

2. ���ı�ע�����**�Ա���еĵ�Ԫ��Ϊ��λ���ӱ�ע��**����һ����Ԫ���ڵ����ֶ����Ϊһ���򣩡���ע��������Ҽ����� `��Ԫ����ʶ��`
   ������ģ���Զ�ʶ��Ԫ���ڵ����֡�

   > ע�⣺�������д��ڿհ׵�Ԫ��ͬ����Ҫʹ��һ����ע��������ʹ�õ�Ԫ��������ͼ���б���һ�¡�

3. **������Ԫ��˳��**��������`��ͼ-��ʾ����` �򿪱�ע����ţ�����������Ҳ��϶� `ʶ����` һ���µ����н����ʹ�ñ�ע���Ű��մ����ң����ϵ��µ�˳�����У��������α�ע��

4. ��ע���ṹ��**���ⲿExcel����У����������ֵĵ�Ԫ����Ϊ�����ʶ������ `1` ��**����֤Excel�еĵ�Ԫ��ϲ������ԭͼ��ͬ���ɣ�������ҪExcel�еĵ�Ԫ��������ͼƬ�е�������ȫ��ͬ��

5. ����JSON��ʽ���ر����б��ͼ���Ӧ��Excel����� `�ļ�`-`��������ע`������gt.txt��ע�ļ���

### 2.3 ע��

[1] PPOCRLabel��**�ļ���**Ϊ������ǵ�λ���򿪴���ǵ�ͼƬ�ļ��к󣬲����ڴ���������ʾͼƬ�������ڵ�� "ѡ���ļ���" ֮��ֱ�ӽ��ļ����µ�ͼƬ���뵽�����С�

[2] ͼƬ״̬��ʾ����ͼƬ�û��Ƿ��ֶ��������δ�ֶ��������Ϊ ��X�����ֶ������Ϊ ���̡������ ���Զ���ע����ť��PPOCRLabel�����״̬Ϊ ���̡� ��ͼƬ���±�ע��

[3] ���������ʶ�𡱺�ģ�ͻ��ͼƬ�е�ʶ�������и��ǡ��������ڴ�֮ǰ�ֶ����Ĺ�ʶ�������п���������ʶ�������䶯��

[4] PPOCRLabel�������ļ������ڱ��ͼƬ�ļ����£�����һ�¼��֣������ֶ������������ݣ�����������������쳣��

|    �ļ���     |                             ˵��                             |
| :-----------: | :----------------------------------------------------------: |
|   Label.txt   | ����ǩ����ֱ������PPOCR���ģ��ѵ�����û�ÿȷ��5�ż�����󣬳��������Զ�д�롣���û��ر�Ӧ�ó�����л��ļ�·����ͬ�������д�롣 |
| fileState.txt | ͼƬ״̬����ļ������浱ǰ�ļ������Ѿ����û��ֶ�ȷ�Ϲ���ͼƬ���ơ� |
|  Cache.cach   |              �����ļ�������ģ���Զ�ʶ��Ľ����              |
|  rec_gt.txt   | ʶ���ǩ����ֱ������PPOCRʶ��ģ��ѵ�������û��ֶ�����˵������ļ��� - "����ʶ����"������� |
|   crop_img    |   ʶ�����ݡ����ռ����и���ͼƬ����rec_gt.txtͬʱ������   |

## 3. ˵��

### 3.1 ��ݼ�

| ��ݼ�              | ˵��                              |
|------------------|---------------------------------|
| Ctrl + shift + R | �Ե�ǰͼƬ�����б������ʶ��                  |
| W                | �½����ο�                           |
| Q  �� Home       | �½�����                           |
| Ctrl + E         | �༭��ѡ���ǩ                         |
| Ctrl + X         |  `--kie` ģʽ�£��޸� Box �Ĺؼ������� |
| Ctrl + R         | ����ʶ����ѡ���                        |
| Ctrl + C         | �����Ʋ�ճ����ѡ�еı�ǿ�                     |
| Ctrl + B         | �������������λ��                     |
| Ctrl + ������    | ��ѡ��ǿ�                           |
| Backspace �� Delete    | ɾ����ѡ��                           |
| Ctrl + V �� End        | ȷ�ϱ���ͼƬ���                        |
| Ctrl + Shift + d | ɾ������ͼƬ                          |
| D                | ��һ��ͼƬ                           |
| A                | ��һ��ͼƬ                           |
| Ctrl++           | ��С                              |
| Ctrl--           | �Ŵ�                              |
| ��������             | �ƶ���ǿ�                           |
| Z��X��C��V��B     | ��ѡ�еı�ǿ򣬵����ƶ��ĸ�����     |

### 3.2 ����ģ��

 - Ĭ��ģ�ͣ�PPOCRLabelĬ��ʹ��PaddleOCR�е���Ӣ�ĳ�����OCRģ�ͣ�֧����Ӣ��������ʶ�𣬶������Լ�⡣

 - ģ�������л����û���ͨ���˵����� "PaddleOCR" - "ѡ��ģ��" �л�����ģ�����ԣ�Ŀǰ֧�ֵ����԰������ġ����ġ����ġ����ġ�����ģ���������ӿɲο�[PaddleOCRģ���б�](https://github.com/PaddlePaddle/PaddleOCR/blob/release/3.0/docs/version3.x/model_list.md).

 - **�Զ���ģ��**������û��뽫����ģ�͸���Ϊ�Լ�������ģ�ͣ�ͨ�����´���ʾ����
 ```
 from paddleocr import PaddleOCR, PPStructureV3

 ocr = PaddleOCR(
  text_detection_model_name='{your_text_det_model_name}',
  text_detection_model_dir='{your_text_det_model_dir}',
  text_recognition_model_name='{your_text_rec_model_name}',
  text_recognition_model_dir='{your_text_rec_model_dir}',  
)

table_ocr = PPStructureV3(
  layout_detection_model_name='{your_layout_det_model_name}',
  layout_detection_model_dir='{your_layout_det_model_dir}',
  chart_recognition_model_name='{your_chart_rec_model_name}',
  chart_recognition_model_dir='{your_chart_rec_model_dir}',
  region_detection_model_name='{your_region_det_model_name}',
  region_detection_model_dir='{your_region_det_model_dir}',
  # ����ģ����ϸ�滻���·�PPStructure���ʵ��������ģ��·������Ϊ�Լ�������ģ��·�����ɡ�
)
 ```
 ͨ���޸�PPOCRLabel.py�����[PaddleOCR���ʵ����](https://github.com/PaddlePaddle/PaddleOCR/blob/release/3.0/paddleocr/_pipelines/ocr.py#L55) ����[PPStructure���ʵ����](https://github.com/PaddlePaddle/PaddleOCR/blob/release/3.0/paddleocr/_pipelines/pp_structurev3.py#L25)ʵ�֣�����ָ�����ģ�ͣ�`self.ocr = PaddleOCR(use_doc_orientation_classify=False, use_textline_orientation=False, use_doc_unwarping=False, device=gpu, lang=lang) `����Ӳ��� `text_detection_model_name`��`text_detection_model_dir` �������Լ���ģ��·�����ɡ�

### 3.3 ������ǽ��

PPOCRLabel֧�����ֵ�����ʽ��

- �Զ�������������ļ� - �Զ�������ǽ�������û�ÿȷ�Ϲ�һ��ͼƬ�������Զ�����ǽ��д��Label.txt�С���δ�����ѡ����⵽�û��ֶ�ȷ�Ϲ�5��ͼƬ������Զ�������

  > Ĭ��������Զ���������Ϊ�ر�״̬

- �ֶ�������������ļ� - ������ǽ�����ֶ�������ǡ�

- �ر�Ӧ�ó��򵼳�

### 3.4 ���ݼ�����

���ն���������������ִ�����ݼ����ֽű���

```
cd ./PPOCRLabel # ��Ŀ¼�л���PPOCRLabel�ļ�����
python gen_ocr_train_val_test.py --trainValTestRatio 6:2:2 --datasetRootPath ../train_data
```

����˵����

- `trainValTestRatio` ��ѵ��������֤�������Լ���ͼ���������ֱ���������ʵ������趨��Ĭ����`6:2:2`

- `datasetRootPath` ��PPOCRLabel��ע���������ݼ����·����Ĭ��·���� `PaddleOCR/train_data` �ָ����ݼ�ǰӦ�����½ṹ��
  ```
  |-train_data
    |-crop_img
      |- word_001_crop_0.png
      |- word_002_crop_0.jpg
      |- word_003_crop_0.jpg
      | ...
    | Label.txt
    | rec_gt.txt
    |- word_001.png
    |- word_002.jpg
    |- word_003.jpg
    | ...
  ```

### 3.5 ������ʾ

- ���ͬʱʹ��whl����װ��paddleocr�������ȼ�����ͨ��paddleocr.py����PaddleOCR�࣬whl��δ����ʱ�ᵼ�³����쳣��

- PPOCRLabel**��֧�ֶ������ļ���**��ͼƬ�����Զ���ע��

- ���Linux�û���������ڴ���������г���**objc[XXXXX]**��ͷ�Ĵ���֤������opencv�汾̫�ߣ����鰲װ4.2�汾��
    ```
    pip install opencv-python==4.2.0.32
    ```
- ���Linux�û���������ڴ���������г���``` qt.qpa.plugin:?Could?not?load?the?Qt?platform?plugin?"xcb"?in?""?even?though it?was?found.``` ��ͷ�Ĵ���
    ```
    pip uninstall opencv-python
    pip uninstall opencv-contrib-python
    pip install opencv-python-headless
    export QT_QPA_PLATFORM=wayland
    ```
- ���Windows�û����������ʹ�ñ��ʶ��ʱ����``` No python win32com. Error: No module named 'win32com'``` ����
    ```
    pip install premailer
    pip install pywin32
    ```
- ������� ```Missing string id``` ��ͷ�Ĵ�����Ҫ���±�����Դ��
    ```
    pyrcc5 -o libs/resources.py resources.qrc
    ```

- �������``` module 'cv2' has no attribute 'INTER_NEAREST'```������Ҫ����ɾ������opencv��ذ���Ȼ�����°�װ4.2.0.32�汾��headless opencv
    ```
    pip install opencv-contrib-python-headless==4.2.0.32
    ```

### 4. �ο�����

1. [Tzutalin. LabelImg. Git code (2015)](https://github.com/tzutalin/labelImg)
2. [PaddleX�ı����/�ı�ʶ������ģ�����ݱ�ע�̳�](https://paddlepaddle.github.io/PaddleX/latest/data_annotations/ocr_modules/text_detection_recognition.html)

