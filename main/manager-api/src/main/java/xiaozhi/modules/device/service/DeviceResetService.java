@ -0,0 +1,118 @@
package xiaozhi.modules.device.service;

import xiaozhi.modules.agent.entity.AgentEntity;
import xiaozhi.modules.device.dto.DeviceResetDTO;
import xiaozhi.modules.device.entity.DeviceEntity;

/**
 * 设备恢复出厂设置服务接口
 * 
 * @author Claude
 * @version 1.0
 * @since 1.0.0
 */
public interface DeviceResetService {

    /**
     * 执行设备恢复出厂设置
     * 清空指定设备的所有使用数据，恢复到刚绑定时的初始状态
     * 
     * @param resetDTO 重置请求参数
     */
    void resetDevice(DeviceResetDTO resetDTO);

    /**
     * 验证重置请求的有效性
     * 
     * @param resetDTO 重置请求参数
     * @return 验证通过返回true，否则抛出异常
     */
    boolean validateResetRequest(DeviceResetDTO resetDTO);

    /**
     * 检查MAC地址格式是否正确
     * 
     * @param macAddress MAC地址
     * @return 格式正确返回true
     */
    boolean isValidMacAddress(String macAddress);

    /**
     * 验证重置确认码是否有效
     * 
     * @param confirmationCode 确认码
     * @return 有效返回true
     */
    boolean isValidResetConfirmationCode(String confirmationCode);

    /**
     * 验证并获取设备信息
     * 
     * @param macAddress 设备MAC地址
     * @return 设备实体
     */
    DeviceEntity validateDeviceForReset(String macAddress);

    /**
     * 验证智能体是否可以重置
     * 
     * @param agentId 智能体ID
     * @return 智能体实体
     */
    AgentEntity validateAgentForReset(String agentId);

    /**
     * 清空聊天记录
     * 
     * @param macAddress 设备MAC地址
     * @param agentId 智能体ID
     * @return 清空的记录数量
     */
    int clearChatHistory(String macAddress, String agentId);

    /**
     * 清空聊天音频数据
     * 
     * @param macAddress 设备MAC地址
     * @param agentId 智能体ID
     * @return 清空的音频记录数量
     */
    int clearChatAudio(String macAddress, String agentId);

    /**
     * 清空声纹信息
     * 
     * @param agentId 智能体ID
     * @return 清空的声纹记录数量
     */
    int clearVoiceprint(String agentId);

    /**
     * 重置智能体记忆
     * 
     * @param agentId 智能体ID
     * @return 是否重置成功
     */
    boolean resetAgentMemory(String agentId);

    /**
     * 清理重置相关的缓存
     * 
     * @param device 设备实体
     * @param agent 智能体实体
     */
    void cleanupAfterReset(DeviceEntity device, AgentEntity agent);

    /**
     * 记录重置操作审计日志
     * 
     * @param resetDTO 重置参数
     * @param device 设备实体
     * @param agent 智能体实体
     * @param success 操作是否成功
     * @param errorMessage 错误信息(如果有)
     * @param clearedCounts 清空的数据统计信息
     */
    void logResetAudit(DeviceResetDTO resetDTO, DeviceEntity device, AgentEntity agent, 
                      boolean success, String errorMessage, String clearedCounts);
}