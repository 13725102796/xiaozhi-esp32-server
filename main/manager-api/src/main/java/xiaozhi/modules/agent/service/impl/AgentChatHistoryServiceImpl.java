package xiaozhi.modules.agent.service.impl;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;

import xiaozhi.common.constant.Constant;
import xiaozhi.common.page.PageData;
import xiaozhi.common.utils.ConvertUtils;
import xiaozhi.common.utils.JsonUtils;
import xiaozhi.modules.agent.Enums.AgentChatHistoryType;
import xiaozhi.modules.agent.dao.AiAgentChatHistoryDao;
import xiaozhi.modules.agent.dto.AgentChatHistoryDTO;
import xiaozhi.modules.agent.dto.AgentChatSessionDTO;
import xiaozhi.modules.agent.entity.AgentChatHistoryEntity;
import xiaozhi.modules.agent.service.AgentChatHistoryService;
import xiaozhi.modules.agent.vo.AgentChatHistoryUserVO;

/**
 * 智能体聊天记录表处理service {@link AgentChatHistoryService} impl
 *
 * @author Goody
 * @version 1.0, 2025/4/30
 * @since 1.0.0
 */
@Service
public class AgentChatHistoryServiceImpl extends ServiceImpl<AiAgentChatHistoryDao, AgentChatHistoryEntity>
        implements AgentChatHistoryService {

    @Override
    public PageData<AgentChatSessionDTO> getSessionListByAgentId(Map<String, Object> params) {
        String agentId = (String) params.get("agentId");
        int page = Integer.parseInt(params.get(Constant.PAGE).toString());
        int limit = Integer.parseInt(params.get(Constant.LIMIT).toString());

        // 构建查询条件
        QueryWrapper<AgentChatHistoryEntity> wrapper = new QueryWrapper<>();
        wrapper.select("session_id", "MAX(created_at) as created_at", "COUNT(*) as chat_count")
                .eq("agent_id", agentId)
                .groupBy("session_id")
                .orderByDesc("created_at");

        // 执行分页查询
        Page<Map<String, Object>> pageParam = new Page<>(page, limit);
        IPage<Map<String, Object>> result = this.baseMapper.selectMapsPage(pageParam, wrapper);

        List<AgentChatSessionDTO> records = result.getRecords().stream().map(map -> {
            AgentChatSessionDTO dto = new AgentChatSessionDTO();
            dto.setSessionId((String) map.get("session_id"));
            dto.setCreatedAt((LocalDateTime) map.get("created_at"));
            dto.setChatCount(((Number) map.get("chat_count")).intValue());
            return dto;
        }).collect(Collectors.toList());

        return new PageData<>(records, result.getTotal());
    }

    @Override
    public List<AgentChatHistoryDTO> getChatHistoryBySessionId(String agentId, String sessionId) {
        // 构建查询条件
        QueryWrapper<AgentChatHistoryEntity> wrapper = new QueryWrapper<>();
        wrapper.eq("agent_id", agentId)
                .eq("session_id", sessionId)
                .orderByAsc("created_at");

        // 查询聊天记录
        List<AgentChatHistoryEntity> historyList = list(wrapper);

        // 转换为DTO
        return ConvertUtils.sourceToTarget(historyList, AgentChatHistoryDTO.class);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteByAgentId(String agentId, Boolean deleteAudio, Boolean deleteText) {
        if (deleteAudio) {
            baseMapper.deleteAudioByAgentId(agentId);
        }
        if (deleteAudio && !deleteText) {
            baseMapper.deleteAudioIdByAgentId(agentId);
        }
        if (deleteText) {
            baseMapper.deleteHistoryByAgentId(agentId);
        }

    }

    @Override
    public List<AgentChatHistoryUserVO> getRecentlyFiftyByAgentId(String agentId) {
        // 构建查询条件(不添加按照创建时间排序，数据本来就是主键越大创建时间越大
        // 不添加这样可以减少排序全部数据在分页的全盘扫描消耗)
        LambdaQueryWrapper<AgentChatHistoryEntity> wrapper = new LambdaQueryWrapper<>();
        wrapper.select(AgentChatHistoryEntity::getContent, AgentChatHistoryEntity::getAudioId)
                .eq(AgentChatHistoryEntity::getAgentId, agentId)
                .eq(AgentChatHistoryEntity::getChatType, AgentChatHistoryType.USER.getValue())
                .isNotNull(AgentChatHistoryEntity::getAudioId)
                // 添加此行，确保查询结果按照创建时间降序排列
                // 使用id的原因：数据形式，id越大的创建时间就越晚，所以使用id的结果和创建时间降序排列结果一样
                // id作为降序排列的优势，性能高，有主键索引，不用在排序的时候重新进行排除扫描比较
                .orderByDesc(AgentChatHistoryEntity::getId); 

        // 构建分页查询，查询前50页数据
        Page<AgentChatHistoryEntity> pageParam = new Page<>(0, 50);
        IPage<AgentChatHistoryEntity> result = this.baseMapper.selectPage(pageParam, wrapper);
        return result.getRecords().stream().map(item -> {
            AgentChatHistoryUserVO vo = ConvertUtils.sourceToTarget(item, AgentChatHistoryUserVO.class);
            // 处理 content 字段，确保只返回聊天内容
            if (vo != null && vo.getContent() != null) {
                vo.setContent(extractContentFromString(vo.getContent()));
            }
            return vo;
        }).toList();
    }

    /**
     * 从 content 字段中提取聊天内容
     * 如果 content 是 JSON 格式（如 {"speaker": "未知说话人", "content": "现在几点了。"}），则提取 content
     * 字段
     * 如果 content 是普通字符串，则直接返回
     * 
     * @param content 原始内容
     * @return 提取的聊天内容
     */
    private String extractContentFromString(String content) {
        if (content == null || content.trim().isEmpty()) {
            return content;
        }

        // 尝试解析为 JSON
        try {
            Map<String, Object> jsonMap = JsonUtils.parseObject(content, Map.class);
            if (jsonMap != null && jsonMap.containsKey("content")) {
                Object contentObj = jsonMap.get("content");
                return contentObj != null ? contentObj.toString() : content;
            }
        } catch (Exception e) {
            // 如果不是有效的 JSON，直接返回原内容
        }

        // 如果不是 JSON 格式或没有 content 字段，直接返回原内容
        return content;
    }

    @Override
    public String getContentByAudioId(String audioId) {
        AgentChatHistoryEntity agentChatHistoryEntity = baseMapper
                .selectOne(new LambdaQueryWrapper<AgentChatHistoryEntity>()
                        .select(AgentChatHistoryEntity::getContent)
                        .eq(AgentChatHistoryEntity::getAudioId, audioId));
        return agentChatHistoryEntity == null ? null : agentChatHistoryEntity.getContent();
    }

    @Override
    public boolean isAudioOwnedByAgent(String audioId, String agentId) {
        // 查询是否有指定音频id和智能体id的数据，如果有且只有一条说明此数据属性此智能体
        Long row = baseMapper.selectCount(new LambdaQueryWrapper<AgentChatHistoryEntity>()
                .eq(AgentChatHistoryEntity::getAudioId, audioId)
                .eq(AgentChatHistoryEntity::getAgentId, agentId));
        return row == 1;
    }

    @Override
    public List<AgentChatHistoryUserVO> getRecentlyFiftyByMacAddress(String macAddress) {
        System.out.println("=== DEBUG: getRecentlyFiftyByMacAddress 开始查询，MAC地址: " + macAddress + " ===");
        
        // 先查询所有该MAC地址的记录（不加限制条件）
        LambdaQueryWrapper<AgentChatHistoryEntity> allWrapper = new LambdaQueryWrapper<>();
        allWrapper.eq(AgentChatHistoryEntity::getMacAddress, macAddress);
        Long totalCount = this.baseMapper.selectCount(allWrapper);
        System.out.println("=== DEBUG: MAC地址 " + macAddress + " 在聊天记录表中总共有 " + totalCount + " 条记录 ===");
        
        if (totalCount > 0) {
            // 查询该MAC地址的记录详细信息（前5条用于调试）
            allWrapper.last("LIMIT 5");
            List<AgentChatHistoryEntity> debugRecords = this.baseMapper.selectList(allWrapper);
            for (AgentChatHistoryEntity record : debugRecords) {
                System.out.println("=== DEBUG: 记录详情 - ID:" + record.getId() + 
                    ", ChatType:" + record.getChatType() + 
                    ", AudioId:" + record.getAudioId() + 
                    ", Content:" + (record.getContent() != null ? record.getContent().substring(0, Math.min(50, record.getContent().length())) + "..." : "null") + " ===");
            }
        }
        
        // 查询USER类型的记录数量
        LambdaQueryWrapper<AgentChatHistoryEntity> userWrapper = new LambdaQueryWrapper<>();
        userWrapper.eq(AgentChatHistoryEntity::getMacAddress, macAddress)
                   .eq(AgentChatHistoryEntity::getChatType, AgentChatHistoryType.USER.getValue());
        Long userCount = this.baseMapper.selectCount(userWrapper);
        System.out.println("=== DEBUG: MAC地址 " + macAddress + " 的USER类型记录有 " + userCount + " 条 ===");
        
        // 查询有AudioId的USER类型记录数量  
        LambdaQueryWrapper<AgentChatHistoryEntity> userWithAudioWrapper = new LambdaQueryWrapper<>();
        userWithAudioWrapper.eq(AgentChatHistoryEntity::getMacAddress, macAddress)
                           .eq(AgentChatHistoryEntity::getChatType, AgentChatHistoryType.USER.getValue())
                           .isNotNull(AgentChatHistoryEntity::getAudioId);
        Long userWithAudioCount = this.baseMapper.selectCount(userWithAudioWrapper);
        System.out.println("=== DEBUG: MAC地址 " + macAddress + " 的USER类型且有AudioId的记录有 " + userWithAudioCount + " 条 ===");
        
        // 如果有AudioId的USER记录数为0，尝试不要求AudioId的查询
        LambdaQueryWrapper<AgentChatHistoryEntity> wrapper = new LambdaQueryWrapper<>();
        if (userWithAudioCount > 0) {
            // 有音频的查询（原逻辑）
            wrapper.select(AgentChatHistoryEntity::getContent, AgentChatHistoryEntity::getAudioId)
                    .eq(AgentChatHistoryEntity::getMacAddress, macAddress)
                    .eq(AgentChatHistoryEntity::getChatType, AgentChatHistoryType.USER.getValue())
                    .isNotNull(AgentChatHistoryEntity::getAudioId)
                    .orderByDesc(AgentChatHistoryEntity::getId);
            System.out.println("=== DEBUG: 使用有音频的查询条件 ===");
        } else {
            // 放宽条件，不要求AudioId（只要是用户消息即可）
            wrapper.select(AgentChatHistoryEntity::getContent, AgentChatHistoryEntity::getAudioId)
                    .eq(AgentChatHistoryEntity::getMacAddress, macAddress)
                    .eq(AgentChatHistoryEntity::getChatType, AgentChatHistoryType.USER.getValue())
                    .orderByDesc(AgentChatHistoryEntity::getId);
            System.out.println("=== DEBUG: 使用放宽的查询条件（不要求AudioId） ===");
        }
        
        // 构建分页查询，查询前50页数据
        Page<AgentChatHistoryEntity> pageParam = new Page<>(0, 50);
        IPage<AgentChatHistoryEntity> result = this.baseMapper.selectPage(pageParam, wrapper);
        
        System.out.println("=== DEBUG: 最终查询结果数量: " + result.getRecords().size() + " ===");
        
        return result.getRecords().stream().map(item -> {
            AgentChatHistoryUserVO vo = ConvertUtils.sourceToTarget(item, AgentChatHistoryUserVO.class);
            // 处理 content 字段，确保只返回聊天内容
            if (vo != null && vo.getContent() != null) {
                vo.setContent(extractContentFromString(vo.getContent()));
            }
            return vo;
        }).collect(Collectors.toList());
    }

    @Override
    public List<AgentChatHistoryDTO> getRecentlyFiftyFullChatByMacAddress(String macAddress) {
        System.out.println("=== DEBUG: getRecentlyFiftyFullChatByMacAddress 开始查询，MAC地址: " + macAddress + " ===");
        
        // 查询所有类型的聊天记录（用户和智能体）
        LambdaQueryWrapper<AgentChatHistoryEntity> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentChatHistoryEntity::getMacAddress, macAddress)
               .orderByAsc(AgentChatHistoryEntity::getId); // 按时间正序排列，保持对话顺序
        
        // 构建分页查询，查询最近50条记录
        Page<AgentChatHistoryEntity> pageParam = new Page<>(1, 50);
        IPage<AgentChatHistoryEntity> result = this.baseMapper.selectPage(pageParam, wrapper);
        
        System.out.println("=== DEBUG: 完整聊天记录查询结果数量: " + result.getRecords().size() + " ===");
        
        return result.getRecords().stream().map(item -> {
            AgentChatHistoryDTO dto = ConvertUtils.sourceToTarget(item, AgentChatHistoryDTO.class);
            // 处理 content 字段，确保只返回聊天内容
            if (dto != null && dto.getContent() != null) {
                dto.setContent(extractContentFromString(dto.getContent()));
            }
            return dto;
        }).collect(Collectors.toList());
    }
}
