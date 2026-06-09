import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  createPromptTemplate,
  deletePromptTemplate,
  fetchPromptTemplates,
  updatePromptTemplate,
} from "../../../lib/api";
import type { PromptTemplate, PromptTemplatePayload } from "../../../types";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const EMPTY_FORM: PromptTemplatePayload = {
  name: "",
  category: "",
  description: "",
  topic_hint: "",
  reference_hint: "",
  instruction: "",
  system_prompt: "",
};

export function XhsPromptTemplatesPage() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState<PromptTemplatePayload>(EMPTY_FORM);

  async function loadTemplates() {
    setIsLoading(true);
    try {
      const result = await fetchPromptTemplates();
      setTemplates(result.items);
      setError(null);
    } catch {
      setError("加载提示词模板失败。");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, []);

  const builtinTemplates = useMemo(() => templates.filter((t) => t.is_builtin), [templates]);
  const customTemplates = useMemo(() => templates.filter((t) => !t.is_builtin), [templates]);

  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  }

  function openEdit(template: PromptTemplate) {
    setEditingId(Number(template.id));
    setForm({
      name: template.name,
      category: template.category,
      description: template.description,
      topic_hint: template.topic_hint,
      reference_hint: template.reference_hint,
      instruction: template.instruction,
      system_prompt: template.system_prompt,
    });
    setModalOpen(true);
  }

  function openDuplicate(template: PromptTemplate) {
    setEditingId(null);
    setForm({
      name: `${template.name} 副本`,
      category: template.category,
      description: template.description,
      topic_hint: template.topic_hint,
      reference_hint: template.reference_hint,
      instruction: template.instruction,
      system_prompt: template.system_prompt,
    });
    setModalOpen(true);
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setError("请填写模板名称。");
      return;
    }
    setIsSaving(true);
    try {
      if (editingId !== null) {
        await updatePromptTemplate(editingId, form);
      } else {
        await createPromptTemplate(form);
      }
      setModalOpen(false);
      setError(null);
      await loadTemplates();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || "保存模板失败。");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await deletePromptTemplate(id);
      await loadTemplates();
    } catch {
      setError("删除模板失败。");
    }
  }

  function renderTemplate(template: PromptTemplate) {
    const editable = !template.is_builtin;
    return (
      <List.Item
        key={String(template.id)}
        actions={
          editable
            ? [
                <Button key="edit" type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(template)}>
                  编辑
                </Button>,
                <Popconfirm key="del" title="删除此模板？" onConfirm={() => handleDelete(Number(template.id))}>
                  <Button type="text" size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>,
              ]
            : [
                <Button key="dup" type="text" size="small" icon={<PlusOutlined />} onClick={() => openDuplicate(template)}>
                  存为我的模板
                </Button>,
              ]
        }
      >
        <List.Item.Meta
          title={
            <Space size={6}>
              <Text strong>{template.name}</Text>
              {template.category && <Tag color="blue">{template.category}</Tag>}
              {template.is_builtin ? <Tag>内置</Tag> : <Tag color="green">自定义</Tag>}
            </Space>
          }
          description={
            <Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 13 }} ellipsis={{ rows: 2, expandable: true, symbol: "展开" }}>
              {template.description || template.system_prompt}
            </Paragraph>
          }
        />
      </List.Item>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <PageHeader
        eyebrow="XHS Prompt Templates"
        title="提示词模板"
        description="管理小红书风格的原创生成模板，内置模板可一键存为自己的副本再编辑。在「草稿工坊 → 生成新草稿」中选用。"
        action={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadTemplates} loading={isLoading}>
              刷新
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              新建模板
            </Button>
          </Space>
        }
      />

      {error && <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} />}

      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin />
        </div>
      ) : (
        <>
          <Card title={`我的模板 (${customTemplates.length})`} size="small">
            {customTemplates.length === 0 ? (
              <Empty description="还没有自定义模板，点「新建模板」或从内置模板存一份副本。" />
            ) : (
              <List itemLayout="horizontal" dataSource={customTemplates} renderItem={renderTemplate} />
            )}
          </Card>

          <Card title={`内置模板 (${builtinTemplates.length})`} size="small">
            <List itemLayout="horizontal" dataSource={builtinTemplates} renderItem={renderTemplate} />
          </Card>
        </>
      )}

      <Modal
        title={editingId !== null ? "编辑模板" : "新建模板"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        okText="保存"
        okButtonProps={{ icon: <SaveOutlined />, loading: isSaving }}
        width={640}
        destroyOnClose
      >
        <Form layout="vertical">
          <Form.Item label="模板名称" required>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：周末探店种草" />
          </Form.Item>
          <Form.Item label="品类">
            <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="如：探店/美食" />
          </Form.Item>
          <Form.Item label="简介">
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="一句话说明这个模板适合写什么" />
          </Form.Item>
          <Form.Item label="选题提示（生成表单的占位示例）">
            <Input value={form.topic_hint} onChange={(e) => setForm({ ...form, topic_hint: e.target.value })} placeholder="如：例如：人均 50 的宝藏日料" />
          </Form.Item>
          <Form.Item label="参考材料提示（占位）">
            <Input value={form.reference_hint} onChange={(e) => setForm({ ...form, reference_hint: e.target.value })} placeholder="如：店名、地址、人均、招牌菜" />
          </Form.Item>
          <Form.Item label="AI 指令（生成时预填）">
            <TextArea value={form.instruction} onChange={(e) => setForm({ ...form, instruction: e.target.value })} rows={3} placeholder="如：突出性价比与招牌亮点，给出避雷建议" />
          </Form.Item>
          <Form.Item label="System Prompt（品类人设/结构，驱动生成风格）">
            <TextArea value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} rows={5} placeholder="你是资深探店博主……" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
