import type { Metadata } from "next";
import { AnnotationWorkbench } from "@/components/annotation-workbench/AnnotationWorkbench";

export const metadata: Metadata = {
  title: "标注工作台 | Finer OS",
  description: "DPO 训练数据人工标注：held-out 评测集 gold 标注与偏好对抽检",
};

export default function AnnotationPage() {
  return <AnnotationWorkbench />;
}
