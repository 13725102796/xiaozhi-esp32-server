package xiaozhi.modules.agent.service;

import java.util.List;
import java.util.Map;

import com.baomidou.mybatisplus.extension.service.IService;

import xiaozhi.common.page.PageData;
import xiaozhi.modules.agent.dto.AgentChatHistoryDTO;
import xiaozhi.modules.agent.dto.AgentChatSessionDTO;
import xiaozhi.modules.agent.entity.AgentChatHistoryEntity;
import xiaozhi.modules.agent.vo.AgentChatHistoryUserVO;

/**
 * 智能体聊天记录表处理service
 *
 * @author Goody
 * @version 1.0, 2025/4/30
 * @since 1.0.0
 */
public interface AgentChatHistoryService extends IService<AgentChatHistoryEntity> {

    /**
     * 根据智能体ID获取会话列表
     *
     * @param params 查询参数，包含agentId、page、limit
     * @return 分页的会话列表
     */
    PageData<AgentChatSessionDTO> getSessionListByAgentId(Map<String, Object> params);

    /**
     * 根据会话ID获取聊天记录列表
     *
     * @param agentId   智能体ID
     * @param sessionId 会话ID
     * @return 聊天记录列表
     */
    List<AgentChatHistoryDTO> getChatHistoryBySessionId(String agentId, String sessionId);

    /**
     * 根据智能体ID删除聊天记录
     *
     * @param agentId     智能体ID
     * @param deleteAudio 是否删除音频
     * @param deleteText  是否删除文本
     */
    void deleteByAgentId(String agentId, Boolean deleteAudio, Boolean deleteText);

    /**
     * 根据智能体ID获取最近50条用户的聊天记录数据（带音频数据）
     *
     * @param agentId 智能体id
     * @return 聊天记录列表（只有用户）
     */
    List<AgentChatHistoryUserVO> getRecentlyFiftyByAgentId(String agentId);

    /**
     * 根据音频数据ID获取聊天内容
     *
     * @param audioId 音频id
     * @return 聊天内容
     */
    String getContentByAudioId(String audioId);


    /**
     * 查询此音频id是否属于此智能体
     *
     * @param audioId 音频id
     * @param agentId 音频id
     * @return T：属于 F：不属于
     */
    boolean isAudioOwnedByAgent(String audioId,String agentId);

    /**
     * 根据MAC地址获取最近50条用户的聊天记录数据（带音频数据）
     *
     * @param macAddress MAC地址
     * @return 聊天记录列表（只有用户）
     */
    List<AgentChatHistoryUserVO> getRecentlyFiftyByMacAddress(String macAddress);

    /**
     * 根据MAC地址获取最近50条完整聊天记录数据（用户+智能体）
     *
     * @param macAddress MAC地址
     * @return 聊天记录列表（用户和智能体消息）
     */
    List<AgentChatHistoryDTO> getRecentlyFiftyFullChatByMacAddress(String macAddress);

    /**
     * 替换聊天记录中的MAC地址
     *
     * @param macAddress 原MAC地址
     * @param newMacAddress 新MAC地址
     * @return 影响的记录数
     */
    int replaceMacAddress(String macAddress, String newMacAddress);
}
