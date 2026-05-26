import streamlit as st
import pandas as pd
import plotly.express as px

# 1. 網頁基本設定
st.set_page_config(page_title="ASRS 物流自動化評估系統", layout="wide")
st.title("📦 ASRS 自動化倉儲物流評估系統")
st.markdown("支援匯入各種格式的 Excel 原始數據，請在下方手動指定對應的欄位，即可自動執行分類評估。")

# 2. 側邊欄：互動參數設定
st.sidebar.header("⚙️ ASRS 設備參數設定")
pallet_limit = st.sidebar.number_input("棧板最長邊限制 (cm)", value=120.0, step=10.0)
tote_l = st.sidebar.number_input("料箱長度上限 (cm)", value=55.0, step=5.0)
tote_w = st.sidebar.number_input("料箱寬度上限 (cm)", value=35.0, step=5.0)
tote_h = st.sidebar.number_input("料箱高度上限 (cm)", value=25.0, step=5.0)

# 3. 檔案上傳區
uploaded_file = st.file_uploader("📂 上傳客戶的 Excel 檔案", type=["xlsx", "xls"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names

        st.divider()
        st.subheader("🛠️ 第一步：資料表與欄位對應")
        st.info("由於各家客戶的表格格式不同，請在下方確認「標題列」位置，並透過下拉選單綁定對應的資料欄位。")

        col1, col2 = st.columns(2)

        # --- 商品主檔設定區 ---
        with col1:
            st.markdown("#### 📦 商品主檔設定")
            item_sheet = st.selectbox("選擇「商品主檔」所在的工作表：", sheet_names, index=0)
            
            # 讓用戶自訂標題列位置 (避免表格上方有空白列導致抓錯)
            item_header = st.number_input("商品主檔的「標題」在 Excel 的第幾列？", min_value=1, value=1) - 1
            
            # 讀取該工作表的欄位名稱
            df_item_raw = pd.read_excel(xls, sheet_name=item_sheet, header=item_header)
            item_cols = [str(c) for c in df_item_raw.columns]

            # 讓用戶自行從下拉選單指定對應欄位
            item_id_col = st.selectbox("對應「商品編號」的欄位：", item_cols)
            item_l_col = st.selectbox("對應「長度」的欄位：", item_cols)
            item_w_col = st.selectbox("對應「寬度」的欄位：", item_cols)
            item_h_col = st.selectbox("對應「高度」的欄位：", item_cols)

        # --- 出貨明細設定區 ---
        with col2:
            st.markdown("#### 🚚 出貨明細設定")
            out_sheet = st.selectbox("選擇「出貨明細」所在的工作表：", sheet_names, index=len(sheet_names)-1 if len(sheet_names)>1 else 0)
            out_header = st.number_input("出貨明細的「標題」在 Excel 的第幾列？", min_value=1, value=1) - 1
            
            df_out_raw = pd.read_excel(xls, sheet_name=out_sheet, header=out_header)
            out_cols = [str(c) for c in df_out_raw.columns]

            out_id_col = st.selectbox("對應出貨「商品編號」的欄位：", out_cols)

        st.divider()
        
        # --- 執行評估運算 ---
        if st.button("🚀 執行 ASRS 評估分析", use_container_width=True):
            
            # 將使用者選擇的動態欄位，統一轉換為系統可辨識的標準資料庫
            df_item = pd.DataFrame()
            df_item['Product_No'] = df_item_raw[item_id_col].astype(str).str.strip()
            df_item['L'] = pd.to_numeric(df_item_raw[item_l_col], errors='coerce')
            df_item['W'] = pd.to_numeric(df_item_raw[item_w_col], errors='coerce')
            df_item['H'] = pd.to_numeric(df_item_raw[item_h_col], errors='coerce')
            
            # 移除沒有編號的空白或無效資料
            df_item = df_item.dropna(subset=['Product_No'])
            df_item = df_item[(df_item['Product_No'] != 'nan') & (df_item['Product_No'] != '')]

            df_outbound = pd.DataFrame()
            df_outbound['Product_No'] = df_out_raw[out_id_col].astype(str).str.strip()
            active_skus = df_outbound['Product_No'].dropna().unique()

            # 執行你的 7 步驟邏輯
            df_item['Status'] = df_item['Product_No'].apply(lambda x: 'Active' if x in active_skus else 'Discontinue')
            df_active = df_item[df_item['Status'] == 'Active'].copy()

            if df_active.empty:
                st.warning("⚠️ 讀取成功，但在出貨明細中沒有比對到與主檔相同的商品編號。請確認欄位是否選錯？")
            else:
                df_active['Max_Edge'] = df_active[['L', 'W', 'H']].max(axis=1)

                def classify_storage(row):
                    if pd.isna(row['Max_Edge']) or row['Max_Edge'] == 0:
                        return '尺寸資料不全'
                    elif row['Max_Edge'] > pallet_limit:
                        return 'Oversize (外場)'
                    elif row['L'] <= tote_l and row['W'] <= tote_w and row['H'] <= tote_h:
                        return '料箱 (Tote)'
                    else:
                        return '棧板 (Pallet)'

                df_active['Storage_Type'] = df_active.apply(classify_storage, axis=1)

                # --- 渲染視覺化圖表與數據 ---
                st.success("✅ 分析完成！")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("總 SKU 數", len(df_item))
                col_b.metric("Active SKU 數", len(df_active))
                
                tote_count = len(df_active[df_active['Storage_Type'] == '料箱 (Tote)'])
                oversize_count = len(df_active[df_active['Storage_Type'] == 'Oversize (外場)'])
                asrs_rate = round(((len(df_active) - oversize_count) / len(df_active)) * 100, 1) if len(df_active) > 0 else 0
                
                col_c.metric("ASRS 可入庫率", f"{asrs_rate} %")
                col_d.metric("料箱適合件數", tote_count)

               st.subheader("📦 儲存型式分佈佔比")
                fig = px.pie(df_active, names='Storage_Type', hole=0.4, color='Storage_Type',
                             color_discrete_map={'料箱 (Tote)':'#2ecc71', '棧板 (Pallet)':'#3498db', 'Oversize (外場)':'#e74c3c', '尺寸資料不全':'#7f8c8d'})
                st.plotly_chart(fig, use_container_width=True)
