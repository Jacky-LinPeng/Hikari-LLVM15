#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件切割和合并工具
用于处理超过GitHub单文件大小限制的文件
"""

import os
import sys
import hashlib
import json
from pathlib import Path

class FileSplitter:
    def __init__(self, chunk_size_mb=95):
        """初始化文件切割器
        
        Args:
            chunk_size_mb: 每个块的大小（MB），默认95MB，确保小于GitHub的100MB限制
        """
        self.chunk_size = chunk_size_mb * 1024 * 1024  # 转换为字节
    
    def calculate_md5(self, file_path):
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def split_file(self, input_file):
        """切割文件
        
        Args:
            input_file: 要切割的文件路径
        
        Returns:
            切割后的文件列表和元数据
        """
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"文件不存在: {input_file}")
        
        file_size = input_path.stat().st_size
        print(f"原文件大小: {file_size / (1024*1024):.2f} MB")
        
        # 计算原文件MD5
        print("正在计算原文件MD5...")
        original_md5 = self.calculate_md5(input_file)
        print(f"原文件MD5: {original_md5}")
        
        # 计算需要的块数
        num_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        print(f"将分割为 {num_chunks} 个块")
        
        chunk_files = []
        chunk_info = {
            "original_file": input_path.name,
            "original_size": file_size,
            "original_md5": original_md5,
            "chunk_size": self.chunk_size,
            "chunks": []
        }
        
        with open(input_file, 'rb') as infile:
            for i in range(num_chunks):
                chunk_filename = f"{input_path.stem}.part{i+1:03d}"
                chunk_path = input_path.parent / chunk_filename
                
                print(f"正在创建块 {i+1}/{num_chunks}: {chunk_filename}")
                
                with open(chunk_path, 'wb') as outfile:
                    remaining = min(self.chunk_size, file_size - i * self.chunk_size)
                    written = 0
                    
                    while written < remaining:
                        chunk_data = infile.read(min(8192, remaining - written))
                        if not chunk_data:
                            break
                        outfile.write(chunk_data)
                        written += len(chunk_data)
                
                # 计算块文件的MD5
                chunk_md5 = self.calculate_md5(chunk_path)
                chunk_size = chunk_path.stat().st_size
                
                chunk_files.append(str(chunk_path))
                chunk_info["chunks"].append({
                    "filename": chunk_filename,
                    "size": chunk_size,
                    "md5": chunk_md5
                })
                
                print(f"  大小: {chunk_size / (1024*1024):.2f} MB, MD5: {chunk_md5}")
        
        # 保存元数据
        metadata_file = input_path.parent / f"{input_path.stem}.split_info.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(chunk_info, f, indent=2, ensure_ascii=False)
        
        print(f"\n切割完成！")
        print(f"元数据文件: {metadata_file}")
        print(f"块文件: {len(chunk_files)} 个")
        
        return chunk_files, str(metadata_file)
    
    def merge_files(self, metadata_file):
        """合并文件
        
        Args:
            metadata_file: 元数据文件路径
        
        Returns:
            合并后的文件路径
        """
        metadata_path = Path(metadata_file)
        if not metadata_path.exists():
            raise FileNotFoundError(f"元数据文件不存在: {metadata_file}")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            chunk_info = json.load(f)
        
        original_filename = chunk_info["original_file"]
        output_path = metadata_path.parent / f"merged_{original_filename}"
        
        print(f"正在合并文件: {original_filename}")
        print(f"目标大小: {chunk_info['original_size'] / (1024*1024):.2f} MB")
        
        # 验证所有块文件是否存在
        missing_chunks = []
        for chunk in chunk_info["chunks"]:
            chunk_path = metadata_path.parent / chunk["filename"]
            if not chunk_path.exists():
                missing_chunks.append(chunk["filename"])
        
        if missing_chunks:
            raise FileNotFoundError(f"缺少块文件: {', '.join(missing_chunks)}")
        
        # 合并文件
        with open(output_path, 'wb') as outfile:
            for i, chunk in enumerate(chunk_info["chunks"]):
                chunk_path = metadata_path.parent / chunk["filename"]
                print(f"正在合并块 {i+1}/{len(chunk_info['chunks'])}: {chunk['filename']}")
                
                # 验证块文件MD5
                chunk_md5 = self.calculate_md5(chunk_path)
                if chunk_md5 != chunk["md5"]:
                    raise ValueError(f"块文件 {chunk['filename']} MD5校验失败")
                
                with open(chunk_path, 'rb') as infile:
                    while True:
                        data = infile.read(8192)
                        if not data:
                            break
                        outfile.write(data)
        
        # 验证合并后文件的MD5
        print("正在验证合并后文件...")
        merged_md5 = self.calculate_md5(output_path)
        if merged_md5 != chunk_info["original_md5"]:
            raise ValueError("合并后文件MD5校验失败")
        
        print(f"\n合并完成！")
        print(f"输出文件: {output_path}")
        print(f"文件大小: {output_path.stat().st_size / (1024*1024):.2f} MB")
        print(f"MD5校验: 通过")
        
        return str(output_path)

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  切割文件: python file_splitter.py split <文件路径> [块大小MB]")
        print("  合并文件: python file_splitter.py merge <元数据文件路径>")
        print("")
        print("示例:")
        print("  python file_splitter.py split Hikari_LLVM19.0.0git_Apple-Silicon-Mac.tar")
        print("  python file_splitter.py merge Hikari_LLVM19.0.0git_Apple-Silicon-Mac.split_info.json")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        if command == "split":
            if len(sys.argv) < 3:
                print("错误: 请指定要切割的文件路径")
                sys.exit(1)
            
            input_file = sys.argv[2]
            chunk_size_mb = 40  # 默认49MB
            
            if len(sys.argv) > 3:
                try:
                    chunk_size_mb = int(sys.argv[3])
                    if chunk_size_mb <= 0 or chunk_size_mb > 49:
                        print("警告: 建议块大小在1-100MB之间")
                except ValueError:
                    print("错误: 块大小必须是数字")
                    sys.exit(1)
            
            splitter = FileSplitter(chunk_size_mb)
            chunk_files, metadata_file = splitter.split_file(input_file)
            
            print(f"\n生成的文件:")
            print(f"- 元数据: {metadata_file}")
            for chunk_file in chunk_files:
                print(f"- 块文件: {chunk_file}")
        
        elif command == "merge":
            if len(sys.argv) < 3:
                print("错误: 请指定元数据文件路径")
                sys.exit(1)
            
            metadata_file = sys.argv[2]
            splitter = FileSplitter()
            output_file = splitter.merge_files(metadata_file)
            print(f"\n合并后文件: {output_file}")
        
        else:
            print(f"错误: 未知命令 '{command}'")
            print("支持的命令: split, merge")
            sys.exit(1)
    
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
