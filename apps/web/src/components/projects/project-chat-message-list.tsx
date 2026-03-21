"use client";

import type { ChatMessage, SessionDetail } from "@/lib/api";

import { ProjectChatMessageCard } from "./project-chat-message-card";
import styles from "./project-chat-client.module.css";

type ProjectChatMessageListProps = {
  selectedSession: SessionDetail;
  isStreamingMessage: boolean;
  expandedSourceLists: Record<string, boolean>;
  latestActionableMessageId: string | null;
  savedExternalUris: Record<string, boolean>;
  onDeleteCard: (messageId: string) => void;
  onOpenSource: (sourceId: string) => void;
  onSaveExternalSource: (url: string) => void;
  onSaveSummary: () => void;
  onToggleSources: (messageId: string) => void;
  sourceIconFor: (item: { source_type: string; canonical_uri: string }) => string | null;
};

export function ProjectChatMessageList({
  selectedSession,
  isStreamingMessage,
  expandedSourceLists,
  latestActionableMessageId,
  savedExternalUris,
  onDeleteCard,
  onOpenSource,
  onSaveExternalSource,
  onSaveSummary,
  onToggleSources,
  sourceIconFor,
}: ProjectChatMessageListProps) {
  return (
    <div className={styles.chatColumn}>
      {selectedSession.messages.length ? (
        <div className={styles.messageStream}>
          {selectedSession.messages.map((item: ChatMessage) => (
            <ProjectChatMessageCard
              key={item.id}
              expanded={!!expandedSourceLists[item.id]}
              isLatestActionable={latestActionableMessageId === item.id}
              isStreamingMessage={isStreamingMessage}
              message={item}
              onDeleteCard={onDeleteCard}
              onOpenSource={onOpenSource}
              onSaveExternalSource={onSaveExternalSource}
              onSaveSummary={onSaveSummary}
              onToggleSources={onToggleSources}
              savedExternalUris={savedExternalUris}
              sourceIconFor={sourceIconFor}
            />
          ))}
        </div>
      ) : (
        <div className={styles.sessionIntro}>
          <p className={styles.emptyEyebrow}>新会话</p>
          <h1>{selectedSession.title}</h1>
          <p>从这个项目里的资料开始提问。需要更完整分析时，可以手动开启深度调研。</p>
        </div>
      )}
    </div>
  );
}
