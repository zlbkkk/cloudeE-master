import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Spin, Empty } from 'antd';
import {
    LineChartOutlined, ProjectOutlined, RocketOutlined,
    ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
    WarningOutlined, FileTextOutlined
} from '@ant-design/icons';
import axios from 'axios';
import { API_BASE } from '../utils/api';
import { Line, Pie, Column } from '@ant-design/plots';

const DASHBOARD_URL = `${API_BASE}dashboard/statistics/`;

const Dashboard = () => {
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState(null);

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        setLoading(true);
        try {
            const response = await axios.get(DASHBOARD_URL);
            console.log('Dashboard 数据:', response.data);
            console.log('Top Projects:', response.data.top_projects);
            setData(response.data);
        } catch (error) {
            console.error('加载统计数据失败:', error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
                <Spin size="large" tip="加载统计数据中..." />
            </div>
        );
    }

    if (!data) {
        return (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
                <Empty description="暂无统计数据" />
            </div>
        );
    }

    const { core_metrics, trend_data, task_trend, top_projects, risk_distribution, recent_analyses, system_health } = data;

    // 自定义简单柱状图渲染（用于数据量少的情况）
    const renderSimpleBarChart = (data) => {
        if (data.length === 0) return null;
        
        const maxCount = Math.max(...data.map(d => d.count));
        const barWidth = 60; // 固定柱子宽度
        const chartHeight = 250;
        
        return (
            <div style={{ 
                display: 'flex', 
                alignItems: 'flex-end', 
                justifyContent: 'center',
                gap: '40px',
                height: `${chartHeight}px`,
                padding: '20px 40px',
            }}>
                {data.map((item, index) => {
                    const barHeight = maxCount > 0 ? (item.count / maxCount) * (chartHeight - 80) : 20;
                    return (
                        <div key={index} style={{ 
                            display: 'flex', 
                            flexDirection: 'column', 
                            alignItems: 'center',
                            gap: '8px'
                        }}>
                            {/* 数值标签 */}
                            <div style={{ 
                                fontSize: '14px', 
                                fontWeight: 'bold', 
                                color: '#666',
                                marginBottom: '4px'
                            }}>
                                {item.count}
                            </div>
                            {/* 柱子 */}
                            <div style={{
                                width: `${barWidth}px`,
                                height: `${barHeight}px`,
                                backgroundColor: '#1890ff',
                                borderRadius: '8px 8px 0 0',
                                transition: 'all 0.3s ease',
                                boxShadow: '0 2px 8px rgba(24, 144, 255, 0.2)',
                            }} />
                            {/* 日期标签 */}
                            <div style={{ 
                                fontSize: '12px', 
                                color: '#999',
                                marginTop: '8px',
                                whiteSpace: 'nowrap'
                            }}>
                                {item.date}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    };

    // 分析趋势图配置 - 使用柱状图（仅用于数据量多的情况）
    const trendConfig = {
        data: trend_data,
        xField: 'date',
        yField: 'count',
        color: '#1890ff',
        columnStyle: {
            radius: [8, 8, 0, 0],
        },
        label: {
            position: 'top',
            style: {
                fill: '#666',
                fontSize: 12,
                fontWeight: 'bold',
            },
        },
        yAxis: {
            min: 0,
            nice: true,
            label: {
                formatter: (v) => Math.round(v),
            },
        },
        xAxis: {
            label: {
                autoRotate: false,
                autoHide: true,
                style: {
                    fontSize: 11,
                },
            },
        },
        tooltip: {
            formatter: (datum) => {
                return { name: '分析次数', value: datum.count };
            },
        },
        meta: {
            date: {
                alias: '日期',
            },
            count: {
                alias: '分析次数',
            },
        },
    };

    // 项目活跃度表格列配置
    const projectColumns = [
        {
            title: '排名',
            key: 'rank',
            width: 60,
            align: 'center',
            render: (text, record, index) => {
                const rankStyle = {
                    display: 'inline-block',
                    width: '24px',
                    height: '24px',
                    lineHeight: '24px',
                    textAlign: 'center',
                    borderRadius: '50%',
                    fontWeight: 'bold',
                    fontSize: '12px',
                };
                
                if (index === 0) {
                    return <span style={{ ...rankStyle, backgroundColor: '#ffd700', color: '#fff' }}>{index + 1}</span>;
                } else if (index === 1) {
                    return <span style={{ ...rankStyle, backgroundColor: '#c0c0c0', color: '#fff' }}>{index + 1}</span>;
                } else if (index === 2) {
                    return <span style={{ ...rankStyle, backgroundColor: '#cd7f32', color: '#fff' }}>{index + 1}</span>;
                } else {
                    return <span style={{ ...rankStyle, backgroundColor: '#f0f0f0', color: '#666' }}>{index + 1}</span>;
                }
            },
        },
        {
            title: '项目名称',
            dataIndex: 'project_name',
            key: 'project_name',
            ellipsis: true,
        },
        {
            title: '分析次数',
            dataIndex: 'count',
            key: 'count',
            width: 300,
            render: (count, record) => {
                const maxCount = top_projects && top_projects.length > 0 ? top_projects[0].count : 1;
                const percentage = (count / maxCount) * 100;
                
                return (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ 
                            flex: 1, 
                            height: '20px', 
                            backgroundColor: '#f0f0f0', 
                            borderRadius: '10px',
                            overflow: 'hidden',
                            position: 'relative'
                        }}>
                            <div style={{
                                width: `${percentage}%`,
                                height: '100%',
                                backgroundColor: '#1890ff',
                                borderRadius: '10px',
                                transition: 'width 0.3s ease',
                            }} />
                        </div>
                        <span style={{ 
                            fontWeight: 'bold', 
                            color: '#1890ff',
                            minWidth: '40px',
                            textAlign: 'right'
                        }}>
                            {count}
                        </span>
                    </div>
                );
            },
        },
    ];

    // 风险分布饼图配置
    const riskData = Object.entries(risk_distribution).map(([level, count]) => ({
        type: `${level} (${count})`, // 直接在类型名称中包含数量
        value: count,
        level: level, // 保留原始等级用于颜色映射
    }));

    const riskConfig = {
        appendPadding: 10,
        data: riskData,
        angleField: 'value',
        colorField: 'type',
        radius: 0.8,
        innerRadius: 0.6,
        label: false, // 禁用饼图上的标签
        statistic: {
            title: {
                content: '总计',
            },
            content: {
                style: {
                    fontSize: '20px',
                },
            },
        },
        legend: {
            position: 'bottom',
        },
        color: (item) => {
            const level = item.level || item.type.split(' ')[0]; // 提取等级名称
            if (level === '高') return '#ff4d4f';
            if (level === '中') return '#faad14';
            if (level === '低') return '#52c41a';
            return '#d9d9d9'; // 未知用灰色
        },
    };

    // 最近分析记录表格列
    const columns = [
        {
            title: '项目名称',
            dataIndex: 'project_name',
            key: 'project_name',
            width: 150,
            ellipsis: true,
        },
        {
            title: '文件名',
            dataIndex: 'file_name',
            key: 'file_name',
            ellipsis: true,
        },
        {
            title: '风险等级',
            dataIndex: 'risk_level',
            key: 'risk_level',
            width: 80,
            render: (level) => {
                // 风险等级映射（英文转中文）
                const levelMap = {
                    'CRITICAL': '高',
                    'HIGH': '高',
                    'MEDIUM': '中',
                    'LOW': '低',
                    'UNKNOWN': '未知'
                };
                const chineseLevel = levelMap[level] || level;
                
                let color = 'green';
                if (chineseLevel === '高') color = 'red';
                else if (chineseLevel === '中') color = 'orange';
                else if (chineseLevel === '未知') color = 'default';
                
                return <Tag color={color}>{chineseLevel}</Tag>;
            },
        },
        {
            title: '分析时间',
            dataIndex: 'created_at',
            key: 'created_at',
            width: 150,
        },
    ];

    return (
        <div style={{ padding: '0' }}>
            {/* 核心指标卡片 */}
            <Row gutter={[16, 16]} style={{ marginBottom: '20px' }}>
                <Col xs={24} sm={12} lg={6}>
                    <Card>
                        <Statistic
                            title="总分析次数"
                            value={core_metrics.total_analyses}
                            prefix={<LineChartOutlined style={{ color: '#1890ff' }} />}
                            valueStyle={{ color: '#1890ff' }}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card>
                        <Statistic
                            title="总项目数"
                            value={core_metrics.total_projects}
                            prefix={<ProjectOutlined style={{ color: '#52c41a' }} />}
                            valueStyle={{ color: '#52c41a' }}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card>
                        <Statistic
                            title="本周分析次数"
                            value={core_metrics.weekly_analyses}
                            prefix={<RocketOutlined style={{ color: '#faad14' }} />}
                            valueStyle={{ color: '#faad14' }}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card>
                        <Statistic
                            title="平均分析时长"
                            value={core_metrics.avg_duration}
                            prefix={<ClockCircleOutlined style={{ color: '#722ed1' }} />}
                            valueStyle={{ color: '#722ed1', fontSize: '20px' }}
                        />
                    </Card>
                </Col>
            </Row>

            {/* 系统健康状态 */}
            {system_health.running_tasks > 0 && (
                <Card
                    size="small"
                    style={{ marginBottom: '20px', backgroundColor: '#e6f7ff', borderColor: '#91d5ff' }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Spin size="small" />
                        <span style={{ fontWeight: 'bold', color: '#1890ff' }}>
                            正在运行 {system_health.running_tasks} 个分析任务
                        </span>
                    </div>
                </Card>
            )}

            {/* 图表区域 */}
            <Row gutter={[16, 16]} style={{ marginBottom: '20px' }}>
                {/* 分析趋势图 */}
                <Col xs={24} lg={12}>
                    <Card title="分析次数趋势（最近30天）" bordered={false}>
                        {trend_data.length > 0 ? (
                            trend_data.length <= 5 ? (
                                // 数据量少时使用自定义简单柱状图
                                renderSimpleBarChart(trend_data)
                            ) : (
                                // 数据量多时使用 Column 图表
                                <Column {...trendConfig} height={300} />
                            )
                        ) : (
                            <Empty description="暂无数据" style={{ padding: '60px 0' }} />
                        )}
                    </Card>
                </Col>

                {/* 项目活跃度 */}
                <Col xs={24} lg={12}>
                    <Card title="最活跃项目 TOP 10" bordered={false}>
                        {top_projects && top_projects.length > 0 ? (
                            <Table
                                columns={projectColumns}
                                dataSource={top_projects}
                                rowKey="project_name"
                                pagination={false}
                                size="small"
                                showHeader={true}
                            />
                        ) : (
                            <Empty description="暂无数据" style={{ padding: '60px 0' }} />
                        )}
                    </Card>
                </Col>
            </Row>

            <Row gutter={[16, 16]}>
                {/* 风险分布 */}
                <Col xs={24} lg={8}>
                    <Card title="风险等级分布" bordered={false}>
                        {riskData.length > 0 ? (
                            <Pie {...riskConfig} height={300} />
                        ) : (
                            <Empty description="暂无数据" style={{ padding: '60px 0' }} />
                        )}
                    </Card>
                </Col>

                {/* 最近分析记录 */}
                <Col xs={24} lg={16}>
                    <Card
                        title={
                            <span>
                                <FileTextOutlined style={{ marginRight: '8px' }} />
                                最近分析记录
                            </span>
                        }
                        bordered={false}
                    >
                        <Table
                            columns={columns}
                            dataSource={recent_analyses}
                            rowKey="id"
                            pagination={false}
                            size="small"
                            scroll={{ y: 300 }}
                        />
                    </Card>
                </Col>
            </Row>
        </div>
    );
};

export default Dashboard;
