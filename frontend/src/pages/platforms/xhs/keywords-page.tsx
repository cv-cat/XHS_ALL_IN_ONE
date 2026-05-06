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
  Col,
  Empty,
  Form,
  Input,
  List,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import { useEffect, useState } from "react";

import { PageHeader } from "../../../components/layout/app-shell";
import {
  createKeywordGroup,
  deleteKeywordGroup,
  fetchKeywordGroup,
  fetchKeywordGroups,
  updateKeywordGroup,
} from "../../../lib/api";
import type { KeywordGroup, KeywordGroupDetail } from "../../../types";

const { Text } = Typography;

function splitKeywords(value: string): string[] {
  return value
    .split(/[,，\n]/)
    .map((keyword) => keyword.trim())
    .filter(Boolean);
}

function joinKeywords(keywords: string[]): string {
  return keywords.join("，");
}

export function XhsKeywordsPage() {
  const [groups, setGroups] = useState<KeywordGroup[]>([]);
  const [detailsByGroup, setDetailsByGroup] = useState<
    Record<number, KeywordGroupDetail>
  >({});
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadGroups() {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchKeywordGroups("xhs");
      setGroups(result.items);
      const details = await Promise.all(
        result.items.map(async (group) => {
          try {
            return [group.id, await fetchKeywordGroup(group.id)] as const;
          } catch {
            return [group.id, undefined] as const;
          }
        })
      );
      setDetailsByGroup(
        Object.fromEntries(
          details.filter(
            (entry): entry is readonly [number, KeywordGroupDetail] =>
              Boolean(entry[1])
          )
        )
      );
    } catch {
      setError("关键词组加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadGroups();
  }, []);

  function resetForm() {
    setEditingGroupId(null);
    setName("");
    setKeywords("");
  }

  function editGroup(group: KeywordGroup) {
    setEditingGroupId(group.id);
    setName(group.name);
    setKeywords(joinKeywords(group.keywords));
  }

  async function saveGroup() {
    const nextKeywords = splitKeywords(keywords);
    if (!name.trim() || nextKeywords.length === 0) {
      setMessage("请填写名称和至少一个关键词。");
      return;
    }
    setIsWorking(true);
    setMessage(null);
    try {
      if (editingGroupId) {
        const updated = await updateKeywordGroup(editingGroupId, {
          name: name.trim(),
          keywords: nextKeywords,
        });
        setGroups((currentGroups) =>
          currentGroups.map((group) =>
            group.id === updated.id ? updated : group
          )
        );
        const detail = await fetchKeywordGroup(updated.id);
        setDetailsByGroup((currentDetails) => ({
          ...currentDetails,
          [updated.id]: detail,
        }));
        setMessage("关键词组已更新。");
      } else {
        const created = await createKeywordGroup({
          platform: "xhs",
          name: name.trim(),
          keywords: nextKeywords,
        });
        setGroups((currentGroups) => [created, ...currentGroups]);
        const detail = await fetchKeywordGroup(created.id);
        setDetailsByGroup((currentDetails) => ({
          ...currentDetails,
          [created.id]: detail,
        }));
        setMessage("关键词组已创建。");
      }
      resetForm();
    } catch {
      setMessage("关键词组保存失败。");
    } finally {
      setIsWorking(false);
    }
  }

  async function removeGroup(groupId: number) {
    setIsWorking(true);
    setMessage(null);
    try {
      await deleteKeywordGroup(groupId);
      setGroups((currentGroups) =>
        currentGroups.filter((group) => group.id !== groupId)
      );
      setDetailsByGroup((currentDetails) => {
        const nextDetails = { ...currentDetails };
        delete nextDetails[groupId];
        return nextDetails;
      });
      if (editingGroupId === groupId) {
        resetForm();
      }
      setMessage("关键词组已删除。");
    } catch {
      setMessage("关键词组删除失败。");
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="XHS Keywords"
        title="关键词组"
        description="维护选题、赛道和品牌关键词组，从已保存笔记中观察命中量和互动机会。"
        action={
          <Button
            icon={<ReloadOutlined />}
            disabled={isLoading}
            onClick={loadGroups}
          >
            刷新
          </Button>
        }
      />

      <Card
        style={{ background: "#1f1f1f", borderColor: "#303030", marginBottom: 24 }}
      >
        <Form layout="inline" style={{ flexWrap: "wrap", gap: 8 }}>
          <Form.Item>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="关键词组名称"
              disabled={isLoading}
              style={{ width: 200 }}
            />
          </Form.Item>
          <Form.Item>
            <Input.TextArea
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="关键词，用逗号或换行分隔"
              disabled={isLoading}
              autoSize={{ minRows: 1, maxRows: 3 }}
              style={{ width: 320 }}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={editingGroupId ? <SaveOutlined /> : <PlusOutlined />}
              disabled={isWorking}
              onClick={() => void saveGroup()}
            >
              {editingGroupId ? "保存修改" : "创建组"}
            </Button>
          </Form.Item>
          {editingGroupId && (
            <Form.Item>
              <Button disabled={isWorking} onClick={resetForm}>
                取消
              </Button>
            </Form.Item>
          )}
        </Form>
      </Card>

      {message && (
        <Alert
          type="info"
          message={message}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}
      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}

      {isLoading ? (
        <div style={{ textAlign: "center", padding: 48 }}>
          <Spin tip="正在加载关键词组..." />
        </div>
      ) : groups.length === 0 ? (
        <Card style={{ background: "#1f1f1f", borderColor: "#303030" }}>
          <Empty description="暂无关键词组。" />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {groups.map((group) => {
            const detail = detailsByGroup[group.id];
            return (
              <Col xs={24} md={12} key={group.id}>
                <Card
                  title={
                    <Space>
                      <Text strong>{group.name}</Text>
                      <Tag color="blue">xhs</Tag>
                    </Space>
                  }
                  style={{ background: "#1f1f1f", borderColor: "#303030" }}
                >
                  <Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
                    {joinKeywords(group.keywords)}
                  </Text>

                  <Row gutter={16} style={{ marginBottom: 16 }}>
                    <Col span={8}>
                      <Statistic
                        title="命中"
                        value={detail?.trend.total_matches ?? 0}
                        suffix="条"
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="互动"
                        value={detail?.trend.total_engagement ?? 0}
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="关键词"
                        value={group.keywords.length}
                        suffix="个"
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                  </Row>

                  {detail?.trend.keywords.length ? (
                    <div
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 8,
                        marginBottom: 16,
                      }}
                    >
                      {detail.trend.keywords.map((kw) => (
                        <Tag key={kw.keyword}>
                          {kw.keyword} · {kw.notes} 条
                        </Tag>
                      ))}
                    </div>
                  ) : null}

                  {detail?.trend.matched_notes.length ? (
                    <List
                      size="small"
                      dataSource={detail.trend.matched_notes.slice(0, 3)}
                      style={{ marginBottom: 16 }}
                      renderItem={(note) => (
                        <List.Item>
                          <List.Item.Meta
                            title={note.title || note.note_id}
                            description={`${note.author_name || "未知作者"} · 互动 ${note.engagement}`}
                          />
                        </List.Item>
                      )}
                    />
                  ) : null}

                  <Space>
                    <Button
                      icon={<EditOutlined />}
                      disabled={isWorking}
                      onClick={() => editGroup(group)}
                    >
                      编辑
                    </Button>
                    <Button
                      icon={<DeleteOutlined />}
                      danger
                      disabled={isWorking}
                      onClick={() => removeGroup(group.id)}
                    >
                      删除
                    </Button>
                  </Space>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );
}
