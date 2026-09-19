#!/data/data/com.termux/files/usr/bin/bash
# Script tự động cài đặt môi trường và chạy AOV Checker trên Termux Android

echo -e "\033[1;36m==============================================================\033[0m"
echo -e "\033[1;32m   ⚔️ CÀI ĐẶT GARENA - AOV CHECKER TRÊN ANDROID (TERMUX) ⚔️   \033[0m"
echo -e "\033[1;36m==============================================================\033[0m"

echo -e "\n\033[1;33m[1/3] Cập nhật gói phần mềm Termux...\033[0m"
pkg update -y && pkg upgrade -y

echo -e "\n\033[1;33m[2/3] Cài đặt Python và các thư viện cần thiết...\033[0m"
pkg install -y python git clang libjpeg-turbo
pip install --upgrade pip
pip install requests urllib3 pillow

echo -e "\n\033[1;32m[3/3] Cài đặt hoàn tất! Khởi động Tool...\033[0m"
python main.py
