import {
  ApiOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  FileImageOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  StarOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Empty,
  Form,
  Input,
  Popconfirm,
  Row,
  Segmented,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "../../components/layout/app-shell";
import {
  createModelConfig,
  deleteModelConfig,
  fetchModelConfigs,
  setDefaultModelConfig,
  testModelConfig,
  updateModelConfig,
} from "../../lib/api";
import type { ModelConfig, ModelConfigPayload, ModelType } from "../../types";

const { Text } = Typography;

const emptyForm: ModelConfigPayload = {
  name: "",
  model_type: "text",
  provider: "openai-compatible",
  model_name: "gpt-5.4",
  base_url: "",
  api_key: "",
  is_default: true,
};

function defaultModelName(type: ModelType): string {
  return type === "text" ? "gpt-5.4" : "";
}

function typeLabel(type: ModelType): string {
  return type === "text" ? "文本模型" : "图片模型";
}

function ModelTypeIcon({ type }: { type: ModelType }) {
  return type === "text" ? <RobotOutlined /> : <FileImageOutlined />;
}

const cardStyle = { background: "#1f1f1f", borderColor: "#303030" };

export function ModelConfigPage() {
  const [configs, setConfigs] = useState<ModelConfig[]>([]);
  const [form, setForm] = useState<ModelConfigPayload>(emptyForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, { status: string; message: string }>>({});

  const grouped = useMemo(
    () => ({
      text: configs.filter((config) => config.model_type === "text"),
      image: configs.filter((config) => config.model_type === "image"),
    }),
    [configs]
  );

  async function loadConfigs() {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchModelConfigs();
      setConfigs(result.items);
    } catch {
      setError("模型配置加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.name.trim() || !form.model_name.trim()) {
      setError("请填写配置名称和模型名称。");
      return;
    }

    setIsSaving(true);
    setMessage(null);
    setError(null);
    const payload = {
      ...form,
      name: form.name.trim(),
      model_name: form.model_name.trim(),
      provider: form.provider.trim(),
      base_url: form.base_url.trim(),
      api_key: form.api_key.trim(),
    };
    try {
      if (editingId) {
        const updated = await updateModelConfig(editingId, payload);
        setConfigs((current) => current.map((c) => c.id === updated.id ? updated : (updated.is_default && c.model_type === updated.model_type ? { ...c, is_default: false } : c)));
        setMessage(`${typeLabel(updated.model_type)}配置已更新。`);
        setEditingId(null);
      } else {
        const created = await createModelConfig(payload);
        setConfigs((current) => {
          const withoutOldDefault = created.is_default
            ? current.map((config) => config.model_type === created.model_type ? { ...config, is_default: false } : config)
            : current;
          return [created, ...withoutOldDefault];
        });
        setMessage(`${typeLabel(created.model_type)}配置已保存。`);
      }
      setForm({ ...emptyForm, model_type: form.model_type });
    } catch {
      setError("模型配置保存失败。");
    } finally {
      setIsSaving(false);
    }
  }

  function handleEdit(config: ModelConfig) {
    setEditingId(config.id);
    setForm({
      name: config.name,
      model_type: config.model_type,
      provider: config.provider,
      model_name: config.model_name,
      base_url: config.base_url,
      api_key: "",
      is_default: config.is_default,
    });
    setMessage(null);
    setError(null);
  }

  function handleCancelEdit() {
    setEditingId(null);
    setForm({ ...emptyForm, model_type: form.model_type });
  }

  async function handleDelete(configId: number) {
    setError(null);
    setMessage(null);
    try {
      await deleteModelConfig(configId);
      setConfigs((current) => current.filter((c) => c.id !== configId));
      if (editingId === configId) { setEditingId(null); setForm({ ...emptyForm, model_type: form.model_type }); }
      setMessage("配置已删除。");
    } catch {
      setError("配置删除失败。");
    }
  }

  async function handleTest(configId: number) {
    setTestingId(configId);
    try {
      const result = await testModelConfig(configId);
      setTestResults((prev) => ({ ...prev, [configId]: { status: result.status, message: result.message } }));
    } catch {
      setTestResults((prev) => ({ ...prev, [configId]: { status: "error", message: "检查请求失败" } }));
    } finally {
      setTestingId(null);
    }
  }

  async function handleSetDefault(config: ModelConfig) {
    setError(null);
    setMessage(null);
    try {
      const updated = await setDefaultModelConfig(config.id);
      setConfigs((current) =>
        current.map((item) =>
          item.model_type === updated.model_type
            ? { ...item, is_default: item.id === updated.id }
            : item
        )
      );
      setMessage(
        `${updated.name} 已设为默认${typeLabel(updated.model_type)}。`
      );
    } catch {
      setError("默认模型切换失败。");
    }
  }

  useEffect(() => {
    void loadConfigs();
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Model Routing"
        title="模型配置"
        description="为改写、生成、封面和图片处理配置用户级文本与图片模型，后续 AI 任务会从默认配置解析调用参数。"
        action={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadConfigs}
            loading={isLoading}
          >
            刷新
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="推荐的 OpenAI 兼容 API 服务"
        description={<>
          <Typography.Link href="https://api.openai-next.com/" target="_blank" rel="noreferrer">api.openai-next.com</Typography.Link> — OpenAI 中转，Base URL: <Typography.Text code>https://api.openai-next.com/v1</Typography.Text><br />
          <Typography.Link href="https://www.volcengine.com/product/doubao" target="_blank" rel="noreferrer">火山引擎（豆包）</Typography.Link> — 字节跳动大模型平台，Base URL: <Typography.Text code>https://ark.cn-beijing.volces.com/api/v3</Typography.Text><br />
          <Typography.Link href="https://bailian.console.aliyun.com/" target="_blank" rel="noreferrer">阿里云百炼</Typography.Link> — 通义千问系列，Base URL: <Typography.Text code>https://dashscope.aliyuncs.com/compatible-mode/v1</Typography.Text>
        </>}
      />

      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}
      {message && (
        <Alert
          type="success"
          message={message}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                {editingId ? <EditOutlined /> : <PlusOutlined />}
                <span>{editingId ? "编辑模型" : "新增模型"}</span>
              </Space>
            }
            extra={editingId ? <Button size="small" onClick={handleCancelEdit}>取消编辑</Button> : undefined}
            style={cardStyle}
          >
            <Segmented
              value={form.model_type}
              options={[
                { label: "文本模型", value: "text" },
                { label: "图片模型", value: "image" },
              ]}
              onChange={(val) =>
                setForm((current) => ({
                  ...current,
                  model_type: val as ModelType,
                  model_name: defaultModelName(val as ModelType),
                }))
              }
              block
              style={{ marginBottom: 20 }}
            />

            <form onSubmit={handleSubmit}>
              <Form layout="vertical" component="div">
                <Form.Item label="配置名称">
                  <Input
                    value={form.name}
                    onChange={(e) =>
                      setForm((current) => ({
                        ...current,
                        name: e.target.value,
                      }))
                    }
                    placeholder="例如：默认文本模型"
                  />
                </Form.Item>
                <Alert message="所有模型需兼容 OpenAI 接口规范" type="info" style={{ marginBottom: 16, fontSize: 12 }} />
                <Form.Item label="模型名称">
                  <Input
                    value={form.model_name}
                    onChange={(e) =>
                      setForm((current) => ({
                        ...current,
                        model_name: e.target.value,
                      }))
                    }
                    placeholder={
                      form.model_type === "text" ? "gpt-4o-mini" : "gpt-image-1"
                    }
                  />
                </Form.Item>
                <Form.Item label="Base URL">
                  <Input
                    value={form.base_url}
                    onChange={(e) =>
                      setForm((current) => ({
                        ...current,
                        base_url: e.target.value,
                      }))
                    }
                    placeholder="https://api.example.com/v1"
                  />
                </Form.Item>
                <Form.Item label="API Key">
                  <Input.Password
                    value={form.api_key}
                    onChange={(e) =>
                      setForm((current) => ({
                        ...current,
                        api_key: e.target.value,
                      }))
                    }
                    placeholder="保存后只显示是否已配置"
                  />
                </Form.Item>
                <Form.Item>
                  <Checkbox
                    checked={form.is_default}
                    onChange={(e) =>
                      setForm((current) => ({
                        ...current,
                        is_default: e.target.checked,
                      }))
                    }
                  >
                    设为该类型默认模型
                  </Checkbox>
                </Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<KeyOutlined />}
                  loading={isSaving}
                  block
                >
                  {isSaving ? "保存中..." : editingId ? "更新配置" : "保存配置"}
                </Button>
              </Form>
            </form>
          </Card>
        </Col>

        <Col xs={24} lg={16}>
          <Row gutter={[16, 16]}>
            {(["text", "image"] as ModelType[]).map((type) => (
              <Col xs={24} md={12} key={type}>
                <Card
                  title={
                    <Space>
                      <ModelTypeIcon type={type} />
                      <span>{typeLabel(type)}</span>
                    </Space>
                  }
                  style={cardStyle}
                >
                  {isLoading ? (
                    <div style={{ textAlign: "center", padding: 24 }}>
                      <Spin tip="正在加载配置..." />
                    </div>
                  ) : grouped[type].length === 0 ? (
                    <Empty
                      image={
                        <ModelTypeIcon type={type} />
                      }
                      description={
                        <div>
                          <Text strong>暂无{typeLabel(type)}</Text>
                          <br />
                          <Text type="secondary">
                            保存一个配置后，AI 改写和生成流程就能读取默认模型。
                          </Text>
                        </div>
                      }
                    />
                  ) : (
                    <Space
                      direction="vertical"
                      style={{ width: "100%" }}
                      size="middle"
                    >
                      {grouped[type].map((config) => (
                        <Card
                          key={config.id}
                          size="small"
                          style={{
                            background: "#262626",
                            borderColor: "#303030",
                          }}
                        >
                          <Space
                            style={{
                              width: "100%",
                              justifyContent: "space-between",
                            }}
                          >
                            <Text strong>{config.name}</Text>
                            {config.is_default && (
                              <Tag
                                icon={<StarOutlined />}
                                color="blue"
                              >
                                默认
                              </Tag>
                            )}
                          </Space>
                          <div style={{ marginTop: 4, marginBottom: 4 }}>
                            <Text>{config.model_name || "未填写模型名称"}</Text>
                          </div>
                          <div
                            style={{
                              marginTop: 8,
                              marginBottom: 8,
                            }}
                          >
                            <Text
                              type="secondary"
                              style={{ fontSize: 12, marginRight: 12 }}
                            >
                              {config.base_url || "未配置 Base URL"}
                            </Text>
                            <Text
                              type="secondary"
                              style={{ fontSize: 12 }}
                            >
                              {config.has_api_key
                                ? "已保存 API Key"
                                : "未保存 API Key"}
                            </Text>
                          </div>
                          <Space size={4} wrap>
                            <Button
                              size="small"
                              icon={<CheckCircleOutlined />}
                              disabled={config.is_default}
                              onClick={() => handleSetDefault(config)}
                            >
                              {config.is_default ? "当前默认" : "设为默认"}
                            </Button>
                            <Button
                              size="small"
                              icon={<ApiOutlined />}
                              loading={testingId === config.id}
                              onClick={() => void handleTest(config.id)}
                            >
                              检查
                            </Button>
                            <Button
                              size="small"
                              icon={<EditOutlined />}
                              onClick={() => handleEdit(config)}
                            >
                              编辑
                            </Button>
                            <Popconfirm title="确定删除此模型配置？" onConfirm={() => void handleDelete(config.id)}>
                              <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
                            </Popconfirm>
                          </Space>
                          {testResults[config.id] && (
                            <div style={{ marginTop: 6 }}>
                              <Tag color={testResults[config.id].status === "ok" ? "success" : "error"}>
                                {testResults[config.id].status === "ok" ? "连接正常" : "连接失败"}
                              </Tag>
                              <Text type="secondary" style={{ fontSize: 11 }}>{testResults[config.id].message}</Text>
                            </div>
                          )}
                        </Card>
                      ))}
                    </Space>
                  )}
                </Card>
              </Col>
            ))}
          </Row>
        </Col>
      </Row>
    </div>
  );
}
