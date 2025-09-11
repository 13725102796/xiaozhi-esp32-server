package xiaozhi.modules.device.service.impl;

import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.regex.Pattern;

import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;

import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import xiaozhi.common.exception.RenException;
import xiaozhi.common.redis.RedisKeys;
import xiaozhi.common.redis.RedisUtils;
import xiaozhi.common.user.UserDetail;
import xiaozhi.modules.agent.entity.AgentChatAudioEntity;
import xiaozhi.modules.agent.entity.AgentChatHistoryEntity;
import xiaozhi.modules.agent.entity.AgentEntity;
import xiaozhi.modules.agent.service.AgentChatAudioService;
import xiaozhi.modules.agent.service.AgentChatHistoryService;
import xiaozhi.modules.agent.service.AgentService;
import xiaozhi.modules.agent.service.AgentVoicePrintService;
import xiaozhi.modules.agent.vo.AgentVoicePrintVO;
import xiaozhi.modules.device.dto.DeviceResetDTO;
import xiaozhi.modules.device.entity.DeviceEntity;
import xiaozhi.modules.device.service.DeviceResetService;
import xiaozhi.modules.device.service.DeviceService;
import xiaozhi.modules.security.user.SecurityUser;

/**
 * 设备恢复出厂设置服务实现类
 * 
 * @author Claude
 * @version 1.0
 * @since 1.0.0
 */
@Slf4j
@Service
@AllArgsConstructor
public class DeviceResetServiceImpl implements DeviceResetService {

    private final DeviceService deviceService;
    private final AgentService agentService;
    private final AgentChatHistoryService agentChatHistoryService;
    private final AgentChatAudioService agentChatAudioService;
    private final AgentVoicePrintService agentVoicePrintService;
    private final RedisUtils redisUtils;

    // MAC地址正则表达式
    private static final Pattern MAC_PATTERN = Pattern.compile("^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$");
    
    // 重置确认码前缀
    private static final String RESET_CONFIRMATION_PREFIX = "RESET_";

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void resetDevice(DeviceResetDTO resetDTO) {
        log.info("开始执行设备恢复出厂设置: MAC地址 {}", resetDTO.getMacAddress());
        
        List<String> clearedInfo = new ArrayList<>();
        
        try {
            // 1. 验证重置请求
            validateResetRequest(resetDTO);
            
            // 2. 获取并验证设备信息
            DeviceEntity device = validateDeviceForReset(resetDTO.getMacAddress());
            
            // 3. 验证智能体信息
            AgentEntity agent = validateAgentForReset(device.getAgentId());
            
            // 4. 执行数据清理
            if (resetDTO.getResetChatHistory()) {
                // 4.1 清空聊天音频数据（需要先删除，因为聊天记录删除后无法找到audioId）
                int audioCount = clearChatAudio(resetDTO.getMacAddress(), agent.getId());
                clearedInfo.add("聊天音频: " + audioCount + "条");
                
                // 4.2 清空聊天记录
                int chatCount = clearChatHistory(resetDTO.getMacAddress(), agent.getId());
                clearedInfo.add("聊天记录: " + chatCount + "条");
            }
            
            if (resetDTO.getResetVoiceprint()) {
                // 4.3 清空声纹信息
                int voiceprintCount = clearVoiceprint(agent.getId());
                clearedInfo.add("声纹信息: " + voiceprintCount + "条");
            }
            
            if (resetDTO.getResetMemory()) {
                // 4.4 重置智能体记忆
                boolean memoryReset = resetAgentMemory(agent.getId());
                clearedInfo.add("智能体记忆: " + (memoryReset ? "已重置" : "重置失败"));
            }
            
            // 5. 清理缓存
            cleanupAfterReset(device, agent);
            
            // 6. 记录成功日志
            String clearedCounts = String.join(", ", clearedInfo);
            logResetAudit(resetDTO, device, agent, true, null, clearedCounts);
            
            log.info("设备恢复出厂设置完成: MAC地址 {}, 清理数据: {}", resetDTO.getMacAddress(), clearedCounts);
            
        } catch (Exception e) {
            log.error("设备恢复出厂设置失败: " + e.getMessage(), e);
            
            // 记录失败日志
            try {
                DeviceEntity device = deviceService.getDeviceByMacAddress(resetDTO.getMacAddress());
                AgentEntity agent = device != null && device.getAgentId() != null ? 
                                   agentService.selectById(device.getAgentId()) : null;
                logResetAudit(resetDTO, device, agent, false, e.getMessage(), "");
            } catch (Exception logError) {
                log.error("记录重置失败日志时发生错误", logError);
            }
            
            throw new RenException("恢复出厂设置失败: " + e.getMessage());
        }
    }

    @Override
    public boolean validateResetRequest(DeviceResetDTO resetDTO) {
        // 1. 基础参数验证
        if (resetDTO == null) {
            throw new RenException("重置请求参数不能为空");
        }
        
        // 2. MAC地址格式验证
        if (!isValidMacAddress(resetDTO.getMacAddress())) {
            throw new RenException("设备MAC地址格式不正确");
        }
        
        // 3. 确认码验证
        if (!isValidResetConfirmationCode(resetDTO.getConfirmationCode())) {
            throw new RenException("重置确认码格式不正确");
        }
        
        // 4. 至少选择一项重置内容
        if (!resetDTO.getResetChatHistory() && !resetDTO.getResetVoiceprint() && !resetDTO.getResetMemory()) {
            throw new RenException("请至少选择一项要重置的内容");
        }
        
        return true;
    }

    @Override
    public boolean isValidMacAddress(String macAddress) {
        return StringUtils.isNotBlank(macAddress) && MAC_PATTERN.matcher(macAddress).matches();
    }

    @Override
    public boolean isValidResetConfirmationCode(String confirmationCode) {
        return StringUtils.isNotBlank(confirmationCode) && 
               confirmationCode.startsWith(RESET_CONFIRMATION_PREFIX) &&
               confirmationCode.length() >= 12; // RESET_ + 至少6位
    }

    @Override
    public DeviceEntity validateDeviceForReset(String macAddress) {
        DeviceEntity device = deviceService.getDeviceByMacAddress(macAddress);
        if (device == null) {
            throw new RenException("设备不存在: " + macAddress);
        }
        
        if (StringUtils.isBlank(device.getAgentId())) {
            throw new RenException("设备未绑定智能体");
        }
        
        // 验证用户权限
        UserDetail user = SecurityUser.getUser();
        if (user == null || user.getId() == null) {
            throw new RenException("用户未登录");
        }
        
        if (!device.getUserId().equals(user.getId())) {
            throw new RenException("无权限操作该设备");
        }
        
        return device;
    }

    @Override
    public AgentEntity validateAgentForReset(String agentId) {
        AgentEntity agent = agentService.selectById(agentId);
        if (agent == null) {
            throw new RenException("智能体不存在: " + agentId);
        }
        
        // 验证用户权限
        UserDetail user = SecurityUser.getUser();
        if (!agent.getUserId().equals(user.getId())) {
            throw new RenException("无权限操作该智能体");
        }
        
        return agent;
    }

    @Override
    public int clearChatHistory(String macAddress, String agentId) {
        log.info("开始清空聊天记录: MAC地址 {}, 智能体ID {}", macAddress, agentId);
        
        QueryWrapper<AgentChatHistoryEntity> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("mac_address", macAddress)
                    .eq("agent_id", agentId);
        
        // 先获取要删除的记录数量
        long count = agentChatHistoryService.count(queryWrapper);
        
        // 执行删除
        boolean result = agentChatHistoryService.remove(queryWrapper);
        
        log.info("聊天记录清空完成: 删除了 {} 条记录, 删除结果: {}", count, result);
        return (int) count;
    }

    @Override
    public int clearChatAudio(String macAddress, String agentId) {
        log.info("开始清空聊天音频数据: MAC地址 {}, 智能体ID {}", macAddress, agentId);
        
        // 1. 先查找所有聊天记录的audioId
        QueryWrapper<AgentChatHistoryEntity> historyQueryWrapper = new QueryWrapper<>();
        historyQueryWrapper.eq("mac_address", macAddress)
                           .eq("agent_id", agentId)
                           .isNotNull("audio_id");
        
        List<AgentChatHistoryEntity> historyList = agentChatHistoryService.list(historyQueryWrapper);
        
        if (historyList.isEmpty()) {
            log.info("没有找到需要清空的聊天音频数据");
            return 0;
        }
        
        // 2. 收集所有audioId
        List<String> audioIds = historyList.stream()
                .map(AgentChatHistoryEntity::getAudioId)
                .filter(StringUtils::isNotBlank)
                .distinct()
                .toList();
        
        if (audioIds.isEmpty()) {
            log.info("没有找到有效的音频ID");
            return 0;
        }
        
        // 3. 删除音频数据
        QueryWrapper<AgentChatAudioEntity> audioQueryWrapper = new QueryWrapper<>();
        audioQueryWrapper.in("id", audioIds);
        
        long count = agentChatAudioService.count(audioQueryWrapper);
        boolean result = agentChatAudioService.remove(audioQueryWrapper);
        
        log.info("聊天音频数据清空完成: 删除了 {} 条记录, 删除结果: {}", count, result);
        return (int) count;
    }

    @Override
    public int clearVoiceprint(String agentId) {
        log.info("开始清空声纹信息: 智能体ID {}", agentId);
        
        // 获取当前用户ID
        UserDetail user = SecurityUser.getUser();
        Long userId = user != null ? user.getId() : null;


        // 获取指定智能体的所有声纹记录
        List<AgentVoicePrintVO> voicePrints = agentVoicePrintService.list(userId, agentId);
        
        int count = 0;
        for (AgentVoicePrintVO voicePrint : voicePrints) {
            // 使用现有的删除方法
            boolean deleted = agentVoicePrintService.delete(userId, voicePrint.getId());
            if (deleted) {
                count++;
            }
        }
        
        log.info("声纹信息清空完成: 删除了 {} 条记录", count);
        return count;
    }

    @Override
    public boolean resetAgentMemory(String agentId) {
        log.info("开始重置智能体记忆: 智能体ID {}", agentId);
        
        // 获取智能体实体
        AgentEntity agent = agentService.selectById(agentId);
        if (agent == null) {
            log.warn("智能体不存在: {}", agentId);
            return false;
        }
        
        // 重置记忆字段
        agent.setSummaryMemory(null);
        agent.setUpdatedAt(new Date());
        
        boolean result = agentService.updateById(agent);
        
        log.info("智能体记忆重置完成: 重置结果 {}", result);
        return result;
    }

    @Override
    public void cleanupAfterReset(DeviceEntity device, AgentEntity agent) {
        log.info("清理重置相关缓存");
        
        try {
            // 1. 清理设备相关缓存
            String deviceKey = "device:config:" + device.getMacAddress();
            redisUtils.delete(deviceKey);
            
            // 2. 清理智能体配置缓存
            String agentConfigKey = "agent:config:" + agent.getId();
            redisUtils.delete(agentConfigKey);
            
            // 3. 清理服务器配置缓存
            redisUtils.delete(RedisKeys.getServerConfigKey());
            
            // 4. 清理智能体设备最后连接时间缓存
            redisUtils.delete(RedisKeys.getAgentDeviceLastConnectedAtById(agent.getId()));
            
            // 5. 清理智能体音频ID缓存（如果有相关缓存）
            String audioPattern = "agent:audio:id:*";
            // 这里可以根据需要清理特定的音频缓存
            
            log.info("缓存清理完成");
        } catch (Exception e) {
            log.warn("清理缓存时发生错误，但不影响重置结果", e);
        }
    }

    @Override
    public void logResetAudit(DeviceResetDTO resetDTO, DeviceEntity device, AgentEntity agent, 
                             boolean success, String errorMessage, String clearedCounts) {
        try {
            UserDetail user = SecurityUser.getUser();
            
            String logMessage = String.format(
                "设备恢复出厂设置操作 - 用户ID: %s, 设备MAC: %s, 智能体ID: %s, 智能体名称: %s, " +
                "重置选项: [聊天记录:%s, 声纹:%s, 记忆:%s], 原因: %s, 结果: %s%s%s",
                user != null ? user.getId() : "未知",
                resetDTO.getMacAddress(),
                agent != null ? agent.getId() : "未知",
                agent != null ? agent.getAgentName() : "未知",
                resetDTO.getResetChatHistory() ? "是" : "否",
                resetDTO.getResetVoiceprint() ? "是" : "否",
                resetDTO.getResetMemory() ? "是" : "否",
                StringUtils.isNotBlank(resetDTO.getReason()) ? resetDTO.getReason() : "未填写",
                success ? "成功" : "失败",
                success && StringUtils.isNotBlank(clearedCounts) ? ", 清理统计: " + clearedCounts : "",
                success ? "" : ", 错误: " + errorMessage
            );
            
            if (success) {
                log.info("[重置审计] {}", logMessage);
            } else {
                log.error("[重置审计] {}", logMessage);
            }
            
            // TODO: 可以在这里将审计日志保存到数据库的审计表中
            
        } catch (Exception e) {
            log.error("记录重置审计日志时发生错误", e);
        }
    }
}