from django.db import models

class AnalysisReport(models.Model):
    task = models.ForeignKey('AnalysisTask', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联任务")
    project_name = models.CharField(max_length=255, verbose_name="项目名称", default="Unknown Project")
    file_name = models.CharField(max_length=255, verbose_name="文件名")
    change_intent = models.TextField(verbose_name="变更意图", null=True, blank=True)
    risk_level = models.CharField(max_length=50, verbose_name="风险等级")
    report_json = models.JSONField(verbose_name="完整报告JSON")
    diff_content = models.TextField(verbose_name="代码Diff", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="分析时间")

    class Meta:
        db_table = 'analysis_report'
        ordering = ['-created_at']
        verbose_name = "分析报告"
        verbose_name_plural = "分析报告"

    def __str__(self):
        return f"{self.file_name} - {self.created_at}"

class AnalysisTask(models.Model):
    STATUS_CHOICES = [
        ('PENDING', '等待中'),
        ('PROCESSING', '进行中'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
    ]
    
    project_name = models.CharField(max_length=255, verbose_name="项目名称")
    mode = models.CharField(max_length=20, default='local', verbose_name="模式")
    source_branch = models.CharField(max_length=255, verbose_name="工作分支", null=True, blank=True)
    target_branch = models.CharField(max_length=255, verbose_name="基准分支", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    log_details = models.TextField(verbose_name="执行日志", null=True, blank=True)

    class Meta:
        db_table = 'analysis_task'
        ordering = ['-created_at']
        verbose_name = "分析任务"
        verbose_name_plural = "分析任务"

    def __str__(self):
        return f"{self.project_name} ({self.status})"
