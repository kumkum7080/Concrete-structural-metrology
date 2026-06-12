import torch
import torch.nn as nn
from torchvision import models

class ConcreteInspectionNet(nn.Module):
    """
    Custom architecture wrapper supporting multiple backbones.
    Uses Concatenated Global Average & Max Pooling to capture both texture
    and localized sharp crack details simultaneously.
    """
    def __init__(self, backbone_name="efficientnet_b0", num_classes=2, pretrained=True):
        super(ConcreteInspectionNet, self).__init__()
        self.backbone_name = backbone_name

        if backbone_name == "efficientnet_b0":
            weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
            base_model = models.efficientnet_b0(weights=weights)
            self.features = base_model.features
            in_features = base_model.classifier[1].in_features
        elif backbone_name == "efficientnet_b2":
            weights = models.EfficientNet_B2_Weights.DEFAULT if pretrained else None
            base_model = models.efficientnet_b2(weights=weights)
            self.features = base_model.features
            in_features = base_model.classifier[1].in_features
        elif backbone_name == "resnet34":
            weights = models.ResNet34_Weights.DEFAULT if pretrained else None
            base_model = models.resnet34(weights=weights)
            self.features = nn.Sequential(*list(base_model.children())[:-2])
            in_features = base_model.fc.in_features
        else:
            # Fallback to efficientnet_b0
            weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
            base_model = models.efficientnet_b0(weights=weights)
            self.features = base_model.features
            in_features = base_model.classifier[1].in_features

        # Concatenated Average and Max pooling
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.maxpool = nn.AdaptiveMaxPool2d(1)

        # In features is doubled due to concatenation of avg and max pool
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.4, inplace=True),
            nn.Linear(in_features * 2, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(p=0.3),
            nn.Linear(512, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        ap = self.avgpool(x)
        mp = self.maxpool(x)
        x = torch.cat([ap, mp], dim=1)
        x = torch.flatten(x, 1)
        x = self.classifier(x)
        return x

